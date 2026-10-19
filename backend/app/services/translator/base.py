"""翻译引擎抽象基类。"""
from abc import ABC, abstractmethod


class BaseTranslator(ABC):
    @abstractmethod
    async def translate(self, text: str, source_lang: str, target_lang: str,
                        glossary: dict[str, str] | None = None) -> str:
        """翻译单段文本。glossary 为 {源术语: 目标术语}，用于约束译名。"""
        ...

    async def translate_batch(self, texts: list[str], source_lang: str, target_lang: str,
                              glossary: dict[str, str] | None = None) -> list[str]:
        """批量翻译，默认逐段调用，子类可覆盖优化。"""
        results = []
        for text in texts:
            results.append(await self.translate(text, source_lang, target_lang, glossary))
        return results
