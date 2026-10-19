"""应用配置，从环境变量读取。"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data.db"
    github_token: str = ""
    github_webhook_secret: str = ""
    github_app_id: int = 0
    github_app_private_key_path: str = ""
    # GitHub OAuth（用户登录，一键提 PR）
    github_client_id: str = ""
    github_client_secret: str = ""
    github_oauth_callback_url: str = "http://localhost:8000/api/auth/callback"
    session_secret: str = "change-me-in-production-please-use-random-string"
    # 翻译引擎
    translator_provider: str = "mock"
    google_api_key: str = ""
    deepl_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# 支持的目标语言
SUPPORTED_LANGUAGES = [
    {"code": "zh", "name": "中文"},
    {"code": "en", "name": "英语"},
    {"code": "ja", "name": "日语"},
    {"code": "ko", "name": "韩语"},
    {"code": "fr", "name": "法语"},
    {"code": "de", "name": "德语"},
    {"code": "es", "name": "西班牙语"},
    {"code": "ru", "name": "俄语"},
]

# 源语言（含自动检测）
SOURCE_LANGUAGES = [{"code": "auto", "name": "自动检测"}] + SUPPORTED_LANGUAGES

# 单任务源内容上限（字节）
MAX_SOURCE_SIZE = 1024 * 1024  # 1MB
