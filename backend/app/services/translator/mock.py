"""Mock 翻译实现，用于开发与测试。"""
from app.services.translator.base import BaseTranslator


class MockTranslator(BaseTranslator):
    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        # 模拟翻译：给原文加前缀，便于识别
        return f"[译:{target_lang}] {text}"
