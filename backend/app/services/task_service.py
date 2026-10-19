"""任务编排服务：状态机流转，串联抓取→解析→翻译→组装。"""
from sqlalchemy.orm import Session
from app.models.task import Task, TaskStatus, ResourceType
from app.models.segment import Segment, SegmentStatus, SegmentType
from app.repositories.task_repo import TaskRepo
from app.repositories.segment_repo import SegmentRepo
from app.services.github_service import GitHubService, GitHubError
from app.services.parser_service import ParserService
from app.services.assembler_service import AssemblerService
from app.services.glossary_service import GlossaryService
from app.services.translation_cache import TranslationCacheService
from app.services.translator import get_translator
from app.config import MAX_SOURCE_SIZE


class TaskService:
    def __init__(self, db: Session):
        self.db = db
        self.task_repo = TaskRepo(db)
        self.segment_repo = SegmentRepo(db)

    def create_task(self, resource_url: str, target_lang: str, source_lang: str) -> Task:
        """创建任务并启动异步处理。"""
        gh = GitHubService()
        try:
            resource = gh.parse_url(resource_url)
        except ValueError as e:
            raise ValueError(str(e))

        task = Task(
            resource_type=resource["type"],
            resource_url=resource_url,
            repo_full_name=resource["repo"],
            resource_number=resource.get("number"),
            source_lang=source_lang,
            target_lang=target_lang,
            status=TaskStatus.CREATED,
        )
        self.task_repo.create(task)
        return task

    async def process_task(self, task_id: str):
        """执行完整翻译流程。"""
        task = self.task_repo.get(task_id)
        if not task:
            return

        gh = GitHubService()
        try:
            # 1. 抓取
            self.task_repo.update_status(task_id, TaskStatus.FETCHING)
            resource = gh.parse_url(task.resource_url)
            content = await gh.fetch_content(resource)

            if len(content.encode("utf-8")) > MAX_SOURCE_SIZE:
                raise GitHubError(f"源内容超过大小上限 {MAX_SOURCE_SIZE // 1024}KB", 400)

            self.task_repo.update_source_content(task_id, content)
            self.task_repo.update_status(task_id, TaskStatus.FETCHED)

            # 2. 解析分段
            self.task_repo.update_status(task_id, TaskStatus.PARSING)
            parser = ParserService()
            parsed = parser.parse(content)
            segments = []
            for idx, ps in enumerate(parsed):
                segments.append(Segment(
                    task_id=task_id,
                    sequence=idx,
                    segment_type=ps.segment_type,
                    translatable=ps.translatable,
                    source_text=ps.source_text,
                    status=SegmentStatus.PENDING,
                ))
            self.segment_repo.bulk_create(segments)

            # 3. 翻译：缓存命中直接复用，未命中的去重后一次批量调用
            self.task_repo.update_status(task_id, TaskStatus.TRANSLATING)
            translator = get_translator()
            glossary = GlossaryService(self.db)
            cache_svc = TranslationCacheService(self.db)
            # 术语表：注入提示词约束译名，同时纳入缓存键（术语表变更后缓存自动失效）
            terms = glossary.get_terms_dict(task.source_lang, task.target_lang) if task.source_lang != "auto" else {}
            glossary_kw = terms or None

            translatable_segs = [s for s in segments if s.translatable]
            texts = [s.source_text for s in translatable_segs]

            translation_map = cache_svc.get_many(texts, task.source_lang, task.target_lang, glossary_kw)
            unique_missing = list(dict.fromkeys(t for t in texts if t not in translation_map))

            if unique_missing:
                try:
                    batch_results = await translator.translate_batch(
                        unique_missing, task.source_lang, task.target_lang, glossary_kw
                    )
                except Exception:
                    batch_results = None  # 整批失败：回退逐条
                if batch_results is None:
                    batch_results = []
                    for t in unique_missing:
                        try:
                            batch_results.append(await translator.translate(
                                t, task.source_lang, task.target_lang, glossary_kw
                            ))
                        except Exception:
                            batch_results.append(None)

                new_map = {t: r for t, r in zip(unique_missing, batch_results) if r is not None}
                if new_map:
                    cache_svc.put_many(
                        new_map, task.source_lang, task.target_lang,
                        model=getattr(translator, "model", None), glossary=glossary_kw,
                    )
                    translation_map.update(new_map)

            failed_count = 0
            for seg in translatable_segs:
                translated = translation_map.get(seg.source_text)
                if translated is None:
                    self.segment_repo.mark_failed(seg.id, "翻译失败")
                    failed_count += 1
                    continue
                # 术语后处理（缓存存的是 LLM 原始输出，术语表随时可调整生效）
                if task.source_lang != "auto":
                    translated = glossary.apply(translated, task.source_lang, task.target_lang)
                self.segment_repo.update_translation(seg.id, translated, SegmentStatus.TRANSLATED)

            # 4. 完成状态
            if failed_count == 0:
                self.task_repo.update_status(task_id, TaskStatus.COMPLETED)
            elif failed_count < len(translatable_segs):
                self.task_repo.update_status(task_id, TaskStatus.PARTIAL_FAILED)
            else:
                self.task_repo.update_status(task_id, TaskStatus.FAILED, "全部可译分段翻译失败")

        except GitHubError as e:
            self.task_repo.update_status(task_id, TaskStatus.FAILED, str(e))
        except Exception as e:
            self.task_repo.update_status(task_id, TaskStatus.FAILED, f"处理失败: {str(e)}")
        finally:
            await gh.aclose()

    def get_task_with_stats(self, task_id: str):
        """获取任务及统计信息。"""
        task = self.task_repo.get(task_id)
        if not task:
            return None
        segments = self.segment_repo.get_by_task(task_id)
        total = len(segments)
        translated = sum(1 for s in segments if s.status in (SegmentStatus.TRANSLATED, SegmentStatus.MANUALLY_EDITED))
        failed = sum(1 for s in segments if s.status == SegmentStatus.FAILED)
        return task, total, translated, failed

    def assemble_result(self, task_id: str) -> str:
        """组装最终译文。"""
        segments = self.segment_repo.get_by_task(task_id)
        return AssemblerService.assemble(segments)

    async def retry_failed(self, task_id: str) -> int:
        """重试失败分段（走缓存 + 批量翻译），返回重试数量。"""
        failed = self.segment_repo.get_failed(task_id)
        if not failed:
            return 0

        task = self.task_repo.get(task_id)
        translator = get_translator()
        glossary = GlossaryService(self.db)
        cache_svc = TranslationCacheService(self.db)
        terms = glossary.get_terms_dict(task.source_lang, task.target_lang) if task.source_lang != "auto" else {}
        glossary_kw = terms or None

        texts = [s.source_text for s in failed]
        translation_map = cache_svc.get_many(texts, task.source_lang, task.target_lang, glossary_kw)
        unique_missing = list(dict.fromkeys(t for t in texts if t not in translation_map))

        if unique_missing:
            try:
                batch_results = await translator.translate_batch(
                    unique_missing, task.source_lang, task.target_lang, glossary_kw
                )
            except Exception:
                batch_results = None
            if batch_results is None:
                batch_results = []
                for t in unique_missing:
                    try:
                        batch_results.append(await translator.translate(
                            t, task.source_lang, task.target_lang, glossary_kw
                        ))
                    except Exception:
                        batch_results.append(None)

            new_map = {t: r for t, r in zip(unique_missing, batch_results) if r is not None}
            if new_map:
                cache_svc.put_many(
                    new_map, task.source_lang, task.target_lang,
                    model=getattr(translator, "model", None), glossary=glossary_kw,
                )
                translation_map.update(new_map)

        retried = 0
        for seg in failed:
            translated = translation_map.get(seg.source_text)
            if translated is None:
                continue
            if task.source_lang != "auto":
                translated = glossary.apply(translated, task.source_lang, task.target_lang)
            self.segment_repo.update_translation(seg.id, translated, SegmentStatus.TRANSLATED)
            retried += 1

        # 重新评估任务状态
        segments = self.segment_repo.get_by_task(task_id)
        remaining_failed = sum(1 for s in segments if s.status == SegmentStatus.FAILED)
        if remaining_failed == 0:
            self.task_repo.update_status(task_id, TaskStatus.COMPLETED)
        else:
            self.task_repo.update_status(task_id, TaskStatus.PARTIAL_FAILED)

        return retried
