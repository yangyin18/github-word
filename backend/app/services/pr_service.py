"""PR 翻译服务：识别翻译请求、触发翻译、回写译文评论。"""
import re
from sqlalchemy.orm import Session
from app.services.task_service import TaskService
from app.services.github_service import GitHubService
from app.models.task import ResourceType

# 翻译请求评论格式：/translate [目标语言]
TRANSLATE_PATTERN = re.compile(r"^/translate(?:\s+(\w{2}))?\s*$", re.MULTILINE)

TRANSLATION_COMMENT_HEADER = "<!-- github-translation-bot -->"


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

    async def handle_pr_event(self, payload: dict, installation_id: int = None):
        """处理 pull_request 事件（opened / synchronize）。"""
        action = payload.get("action")
        if action not in ("opened", "synchronize"):
            return

        pr = payload.get("pull_request", {})
        repo = payload["repository"]["full_name"]
        pr_number = pr["number"]
        # 仅当 PR 描述中包含 /translate 时自动触发
        body = pr.get("body") or ""
        target_lang = self.parse_translate_request(body)
        if not target_lang:
            return

        await self._run_translation(repo, pr_number, target_lang, installation_id)

    async def handle_comment_event(self, payload: dict, installation_id: int = None):
        """处理 issue_comment 事件（仅 PR 评论）。"""
        action = payload.get("action")
        if action != "created":
            return

        comment = payload.get("comment", {})
        body = comment.get("body") or ""
        target_lang = self.parse_translate_request(body)
        if not target_lang:
            return

        repo = payload["repository"]["full_name"]
        # PR 的 issue 评论事件中，pull_request 字段存在则为 PR
        pr_data = payload.get("issue", {}).get("pull_request")
        if not pr_data:
            return  # 普通 Issue 评论，忽略
        pr_number = payload["issue"]["number"]

        await self._run_translation(repo, pr_number, target_lang, installation_id)

    async def _run_translation(self, repo: str, pr_number: int, target_lang: str, installation_id: int = None):
        """执行翻译并回写评论。"""
        resource_url = f"https://github.com/{repo}/pull/{pr_number}"
        try:
            task = self.task_service.create_task(resource_url, target_lang, "auto")
        except ValueError as e:
            try:
                await self._post_comment(repo, pr_number, f"翻译失败：{e}", installation_id)
            except Exception:
                pass
            return

        # 同步等待翻译完成（PR 场景下需要拿到结果再发评论）
        await self.task_service.process_task(task.id)

        # 获取译文
        translated_md = self.task_service.assemble_result(task.id)
        comment_body = f"{TRANSLATION_COMMENT_HEADER}\n## 翻译结果\n\n{translated_md}"

        # 发布评论失败不影响翻译结果（任务已完成，可通过 API 查看）
        try:
            await self._post_or_update_comment(repo, pr_number, comment_body, installation_id)
        except Exception as e:
            import logging
            logging.warning(f"发布 PR 评论失败（task={task.id}）: {e}")

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
