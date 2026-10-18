"""GitHub API 服务：解析资源 URL 并抓取公开内容。"""
import re
import base64
from typing import Optional
import httpx

from app.config import settings
from app.models.task import ResourceType
from app.services.github_app_auth import GitHubAppAuth

GITHUB_API_BASE = "https://api.github.com"

# URL 匹配模式
ISSUE_PATTERN = re.compile(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)")
PR_PATTERN = re.compile(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)")
README_PATTERN = re.compile(r"github\.com/([^/]+)/([^/]+)(?:$|/?$|/blob/[^/]+/README)")


class GitHubError(Exception):
    def __init__(self, message: str, status_code: int = 0, retry_after: int = 0):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class GitHubService:
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )
        # 默认使用 PAT（若有）
        if settings.github_token:
            self.client.headers["Authorization"] = f"Bearer {settings.github_token}"
        self._app_auth = GitHubAppAuth()

    async def aclose(self):
        await self.client.aclose()

    async def _auth_headers(self, installation_id: int = None) -> dict:
        """获取鉴权头：优先 App Installation Token，回退 PAT。"""
        if installation_id and self._app_auth.enabled:
            token = await self._app_auth.get_installation_token(installation_id)
            return {"Authorization": f"Bearer {token}"}
        return {}

    def parse_url(self, url: str) -> dict:
        """解析 GitHub URL，返回 {repo, type, number}。"""
        m = PR_PATTERN.search(url)
        if m:
            return {
                "repo": f"{m.group(1)}/{m.group(2)}",
                "type": ResourceType.PULL_REQUEST,
                "number": int(m.group(3)),
            }
        m = ISSUE_PATTERN.search(url)
        if m:
            return {
                "repo": f"{m.group(1)}/{m.group(2)}",
                "type": ResourceType.ISSUE,
                "number": int(m.group(3)),
            }
        m = README_PATTERN.search(url)
        if m:
            return {
                "repo": f"{m.group(1)}/{m.group(2)}",
                "type": ResourceType.README,
                "number": None,
            }
        raise ValueError("无法识别的 GitHub 资源 URL，仅支持 Issue / Pull Request / 仓库 README")

    async def _check_repo_public(self, repo: str):
        """校验仓库是否公开。"""
        resp = await self.client.get(f"/repos/{repo}")
        if resp.status_code == 404:
            raise GitHubError("仓库不存在或无权限访问", 404)
        if resp.status_code == 403:
            retry_after = self._parse_rate_limit(resp)
            raise GitHubError("GitHub API 速率限制，请稍后重试", 403, retry_after)
        resp.raise_for_status()
        data = resp.json()
        if data.get("private"):
            raise GitHubError("仅支持公开 GitHub 资源", 403)

    def _parse_rate_limit(self, resp: httpx.Response) -> int:
        reset = resp.headers.get("X-RateLimit-Reset")
        if reset:
            import time
            return max(0, int(reset) - int(time.time()))
        return 60

    async def fetch_content(self, resource: dict) -> str:
        """根据资源类型抓取内容，返回 Markdown 原文。"""
        repo = resource["repo"]
        await self._check_repo_public(repo)

        rtype = resource["type"]
        if rtype in (ResourceType.ISSUE, ResourceType.PULL_REQUEST):
            number = resource["number"]
            resp = await self.client.get(f"/repos/{repo}/issues/{number}")
            self._check_resp(resp)
            data = resp.json()
            title = data.get("title", "")
            body = data.get("body") or ""
            return f"# {title}\n\n{body}"

        if rtype == ResourceType.README:
            resp = await self.client.get(f"/repos/{repo}/readme")
            self._check_resp(resp)
            content_b64 = resp.json().get("content", "")
            return base64.b64decode(content_b64).decode("utf-8")

        raise GitHubError(f"不支持的资源类型: {rtype}", 400)

    def _check_resp(self, resp: httpx.Response):
        if resp.status_code == 403:
            retry_after = self._parse_rate_limit(resp)
            raise GitHubError("GitHub API 速率限制，请稍后重试", 403, retry_after)
        if resp.status_code == 404:
            raise GitHubError("资源不存在", 404)
        resp.raise_for_status()

    async def post_pr_comment(self, repo: str, pr_number: int, body: str, installation_id: int = None):
        """发布 PR 评论。"""
        headers = await self._auth_headers(installation_id)
        resp = await self.client.post(
            f"/repos/{repo}/issues/{pr_number}/comments",
            json={"body": body},
            headers=headers,
        )
        self._check_resp(resp)
        return resp.json()

    async def update_comment(self, repo: str, comment_id: int, body: str, installation_id: int = None):
        """更新已有评论。"""
        headers = await self._auth_headers(installation_id)
        resp = await self.client.patch(
            f"/repos/{repo}/issues/comments/{comment_id}",
            json={"body": body},
            headers=headers,
        )
        self._check_resp(resp)
        return resp.json()

    async def list_issue_comments(self, repo: str, number: int, installation_id: int = None) -> list:
        """列出 Issue/PR 的评论。"""
        headers = await self._auth_headers(installation_id)
        resp = await self.client.get(
            f"/repos/{repo}/issues/{number}/comments",
            headers=headers,
        )
        self._check_resp(resp)
        return resp.json()
