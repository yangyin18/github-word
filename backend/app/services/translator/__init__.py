"""翻译引擎工厂，根据配置创建对应实例。"""
from app.config import settings
from app.services.translator.base import BaseTranslator
from app.services.translator.mock import MockTranslator
from app.services.translator.openrouter import OpenRouterTranslator


def get_translator() -> BaseTranslator:
    provider = settings.translator_provider.lower()
    if provider == "mock":
        return MockTranslator()
    if provider == "openrouter":
        return OpenRouterTranslator()
    # 后续可扩展 google / deepl
    raise ValueError(f"Unsupported translator provider: {provider}")
