"""翻译引擎抽象基类。"""
from abc import ABC, abstractmethod


class BaseTranslator(ABC):
    @abstractmethod
    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """翻译单段文本。"""
        ...

    async def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """批量翻译，默认逐段调用，子类可覆盖优化。"""
        results = []
        for text in texts:
            results.append(await self.translate(text, source_lang, target_lang))
        return results
