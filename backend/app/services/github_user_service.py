"""GitHub 用户操作服务：用 user token 调用 Contents/Pulls API。

支持：列仓库、列目录、读文件、创建分支、提交文件、开 PR。
"""
import base64
import httpx

GITHUB_API_BASE = "https://api.github.com"


class GitHubUserError(Exception):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class GitHubUserService:
    def __init__(self, access_token: str):
        self.token = access_token
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=GITHUB_API_BASE, headers=self._headers, timeout=30)

    async def list_repos(self, page: int = 1, per_page: int = 50) -> list:
        """列出用户的仓库（含私有）。"""
        async with self._client() as c:
            resp = await c.get(
                "/user/repos",
                params={"page": page, "per_page": per_page, "sort": "updated"},
            )
            self._check(resp)
            return resp.json()

    async def get_repo(self, repo: str) -> dict:
        """获取仓库信息。"""
        async with self._client() as c:
            resp = await c.get(f"/repos/{repo}")
            self._check(resp)
            return resp.json()

    async def list_contents(self, repo: str, path: str = "", ref: str = None) -> list:
        """列出仓库指定路径的文件/目录。"""
        async with self._client() as c:
            params = {}
            if ref:
                params["ref"] = ref
            resp = await c.get(f"/repos/{repo}/contents/{path}", params=params)
            self._check(resp)
            return resp.json()

    async def get_file_content(self, repo: str, path: str, ref: str = None) -> dict:
        """读取文件内容，返回 {content, sha, size, name, path}。"""
        async with self._client() as c:
            params = {}
            if ref:
                params["ref"] = ref
            resp = await c.get(f"/repos/{repo}/contents/{path}", params=params)
            self._check(resp)
            data = resp.json()
            content_b64 = data.get("content", "")
            content = base64.b64decode(content_b64).decode("utf-8") if content_b64 else ""
            return {
                "content": content,
                "sha": data["sha"],
                "size": data["size"],
                "name": data["name"],
                "path": data["path"],
                "default_branch": None,  # 由调用方补充
            }

    async def get_default_branch(self, repo: str) -> str:
        """获取仓库默认分支名。"""
        data = await self.get_repo(repo)
        return data["default_branch"]

    async def create_branch(self, repo: str, branch: str, from_branch: str) -> dict:
        """基于 from_branch 创建新分支。"""
        # 先拿源分支的最新 commit sha
        async with self._client() as c:
            ref_resp = await c.get(f"/repos/{repo}/git/ref/heads/{from_branch}")
            self._check(ref_resp)
            sha = ref_resp.json()["object"]["sha"]

            create_resp = await c.post(
                f"/repos/{repo}/git/refs",
                json={"ref": f"refs/heads/{branch}", "sha": sha},
            )
            self._check(create_resp)
            return create_resp.json()

    async def create_or_update_file(
        self, repo: str, path: str, content: str, branch: str,
        message: str, sha: str = None,
    ) -> dict:
        """创建或更新文件（创建不传 sha，更新需传 sha）。"""
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        async with self._client() as c:
            resp = await c.put(f"/repos/{repo}/contents/{path}", json=payload)
            self._check(resp)
            return resp.json()

    async def create_pull_request(
        self, repo: str, title: str, head: str, base: str, body: str = "",
    ) -> dict:
        """创建 Pull Request。"""
        async with self._client() as c:
            resp = await c.post(
                f"/repos/{repo}/pulls",
                json={"title": title, "head": head, "base": base, "body": body},
            )
            self._check(resp)
            return resp.json()

    def _check(self, resp: httpx.Response):
        if resp.status_code in (401, 403):
            raise GitHubUserError(
                f"GitHub API 鉴权失败 ({resp.status_code})，请重新登录", resp.status_code
            )
        if resp.status_code == 404:
            raise GitHubUserError("资源不存在", 404)
        resp.raise_for_status()
