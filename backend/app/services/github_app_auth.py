"""GitHub App 鉴权：JWT 换取 Installation Token。

依赖：PyJWT, cryptography
安装：pip install PyJWT cryptography

若未安装或未配置 App，可使用 GITHUB_TOKEN（PAT）直接调用。
"""
import time
import jwt
import httpx
from cryptography.hazmat.primitives import serialization

from app.config import settings


class GitHubAppAuth:
    def __init__(self):
        self.app_id = settings.github_app_id
        self.private_key_path = settings.github_app_private_key_path
        self._private_key = None

    @property
    def enabled(self) -> bool:
        return bool(self.app_id and self.private_key_path)

    def _load_private_key(self):
        if self._private_key is None:
            with open(self.private_key_path, "rb") as f:
                self._private_key = serialization.load_pem_private_key(f.read(), password=None)
        return self._private_key

    def _make_jwt(self) -> str:
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 600, "iss": str(self.app_id)}
        return jwt.encode(payload, self._load_private_key(), algorithm="RS256")

    async def get_installation_token(self, installation_id: int) -> str:
        """用 JWT 换取短期 Installation Token（有效期 1 小时）。"""
        jwt_token = self._make_jwt()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            resp.raise_for_status()
            return resp.json()["token"]


def verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """校验 GitHub Webhook 签名 (X-Hub-Signature-256)。"""
    if not secret:
        return True  # 未配置 secret 时跳过校验（仅本地开发）
    import hmac
    import hashlib
    expected = "sha256=" + hmac.new(secret.encode(), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
