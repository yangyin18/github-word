"""PR 翻译服务：识别翻译请求、触发翻译、回写译文评论。"""
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.task import Task, TaskStatus
from app.services.task_service import TaskService
from app.services.github_service import GitHubService

# 翻译请求评论格式：/translate [目标语言]
TRANSLATE_PATTERN = re.compile(r"^/translate(?:\s+(\w{2}))?\s*$", re.MULTILINE)

TRANSLATION_COMMENT_HEADER = "<!-- github-translation-bot -->"

# 防重窗口：同资源同语言在该时间内的进行中任务视为重复
DEDUP_WINDOW_MINUTES = 10

logger = logging.getLogger(__name__)

# 进行中的任务状态
_ACTIVE_STATUSES = (
    TaskStatus.CREATED, TaskStatus.FETCHING, TaskStatus.FETCHED,
    TaskStatus.PARSING, TaskStatus.TRANSLATING,
)


async def run_translation_job(repo: str, pr_number: int, target_lang: str, installation_id: int = None):
    """后台任务入口：自建数据库会话，执行翻译并回写评论。"""
    db = SessionLocal()
    try:
        service = PRService(db)
        await service.run_translation(repo, pr_number, target_lang, installation_id)
    except Exception:
        logger.exception("后台翻译任务失败 repo=%s pr=%s", repo, pr_number)
    finally:
        db.close()


class PRService:
    def __init__(self, db: Session):
        self.db = db
        self.task_service = TaskService(db)

    @staticmethod
    def parse_translate_request(comment_body: str) -> str | None:
        """从评论体中解析翻译请求，返回目标语言（默认 zh）。"""
        m = TRANSLATE_PATTERN.search(comment_body.strip())
        if not m:
            return None
        return m.group(1) or "zh"

    async def run_translation(self, repo: str, pr_number: int, target_lang: str, installation_id: int = None):
        """执行翻译并回写评论（带防重检查）。"""
        resource_url = f"https://github.com/{repo}/pull/{pr_number}"

        # 防重：同资源同语言已有进行中任务（10 分钟窗口内）则跳过，避免 webhook 重试导致重复翻译
        cutoff = datetime.utcnow() - timedelta(minutes=DEDUP_WINDOW_MINUTES)
        active = (
            self.db.query(Task)
            .filter(
                Task.resource_url == resource_url,
                Task.target_lang == target_lang,
                Task.status.in_(_ACTIVE_STATUSES),
                Task.updated_at >= cutoff,
            )
            .first()
        )
        if active:
            logger.info("跳过重复翻译请求 repo=%s pr=%s lang=%s（已有进行中任务 %s）",
                        repo, pr_number, target_lang, active.id)
            return

        try:
            task = self.task_service.create_task(resource_url, target_lang, "auto")
        except ValueError as e:
            try:
                await self._post_comment(repo, pr_number, f"翻译失败：{e}", installation_id)
            except Exception:
                pass
            return

        await self.task_service.process_task(task.id)

        # 获取译文
        translated_md = self.task_service.assemble_result(task.id)
        comment_body = f"{TRANSLATION_COMMENT_HEADER}\n## 翻译结果\n\n{translated_md}"

        # 发布评论失败不影响翻译结果（任务已完成，可通过 API 查看）
        try:
            await self._post_or_update_comment(repo, pr_number, comment_body, installation_id)
        except Exception as e:
            logger.warning(f"发布 PR 评论失败（task={task.id}）: {e}")

    async def _post_or_update_comment(self, repo: str, pr_number: int, body: str, installation_id: int = None):
        """发布评论，若已有 bot 评论则更新。"""
        gh = GitHubService()
        try:
            # 查找已有 bot 评论
            existing_id = await self._find_bot_comment(gh, repo, pr_number, installation_id)
            if existing_id:
                await gh.update_comment(repo, existing_id, body, installation_id)
            else:
                await gh.post_pr_comment(repo, pr_number, body, installation_id)
        finally:
            await gh.aclose()

    async def _find_bot_comment(self, gh: GitHubService, repo: str, pr_number: int, installation_id: int = None) -> int | None:
        """查找带 bot 标记的已有评论 ID。"""
        comments = await gh.list_issue_comments(repo, pr_number, installation_id)
        for c in comments:
            if TRANSLATION_COMMENT_HEADER in (c.get("body") or ""):
                return c["id"]
        return None

    async def _post_comment(self, repo: str, pr_number: int, body: str, installation_id: int = None):
        gh = GitHubService()
        try:
            await gh.post_pr_comment(repo, pr_number, body, installation_id)
        finally:
            await gh.aclose()
