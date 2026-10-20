"""GitHub App 鉴权：JWT 换取 Installation Token。

依赖：PyJWT, cryptography
安装：pip install PyJWT cryptography

若未安装或未配置 App，可使用 GITHUB_TOKEN（PAT）直接调用。
"""
import asyncio
import time
from datetime import datetime

import jwt
import httpx
from cryptography.hazmat.primitives import serialization

from app.config import settings

# Installation Token 模块级缓存：{installation_id: (token, 过期时间戳)}
# 跨请求实例共享，避免每次 API 调用都重新签 JWT 换 token
_token_cache: dict[int, tuple[str, float]] = {}
_token_lock = asyncio.Lock()

# 提前刷新窗口：过期前 5 分钟即视为失效
_REFRESH_MARGIN = 300


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
        """获取 Installation Token：优先命中缓存，过期前 5 分钟自动刷新。"""
        cached = _token_cache.get(installation_id)
        if cached and cached[1] > time.time() + _REFRESH_MARGIN:
            return cached[0]

        async with _token_lock:
            # 双重检查：并发等待锁期间可能已被其他协程刷新
            cached = _token_cache.get(installation_id)
            if cached and cached[1] > time.time() + _REFRESH_MARGIN:
                return cached[0]

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
                data = resp.json()

            token = data["token"]
            _token_cache[installation_id] = (token, self._parse_expires_at(data.get("expires_at")))
            return token

    @staticmethod
    def _parse_expires_at(expires_at: str | None) -> float:
        """解析 GitHub 返回的过期时间（ISO 8601），缺省按 1 小时。"""
        if expires_at:
            try:
                return datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp()
            except ValueError:
                pass
        return time.time() + 3600

    async def get_first_installation_id(self) -> int:
        """获取 App 的第一个安装 ID（用于未指定 installation 时的默认鉴权）。"""
        jwt_token = self._make_jwt()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.github.com/app/installations",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            resp.raise_for_status()
            installations = resp.json()
            if installations:
                return installations[0]["id"]
        return None


def verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """校验 GitHub Webhook 签名 (X-Hub-Signature-256)。"""
    if not secret:
        return True  # 未配置 secret 时跳过校验（仅本地开发）
    import hmac
    import hashlib
    expected = "sha256=" + hmac.new(secret.encode(), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
