"""GitHub OAuth 服务：管理用户登录、token 获取与验证。"""
import httpx
from urllib.parse import urlencode
from app.config import settings

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE = "https://api.github.com"


class OAuthService:
    @staticmethod
    def get_authorize_url(state: str) -> str:
        """构造 GitHub 授权跳转 URL。"""
        params = {
            "client_id": settings.github_client_id,
            "redirect_uri": settings.github_oauth_callback_url,
            "state": state,
            "allow_signup": "true",
        }
        return f"{GITHUB_AUTH_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_code(code: str) -> str:
        """用 code 换取 access_token。"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GITHUB_TOKEN_URL,
                json={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise ValueError(f"OAuth 失败: {data.get('error_description', data['error'])}")
            return data["access_token"]

    @staticmethod
    async def get_user_info(access_token: str) -> dict:
        """获取当前登录用户信息。"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GITHUB_API_BASE}/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "login": data["login"],
                "name": data.get("name") or data["login"],
                "avatar_url": data.get("avatar_url", ""),
                "html_url": data.get("html_url", ""),
            }
