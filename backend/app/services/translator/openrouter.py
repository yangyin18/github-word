"""OpenRouter 翻译实现：通过 OpenAI 兼容接口调用大模型翻译。"""
import re

import httpx
from app.config import settings
from app.services.translator.base import BaseTranslator

# 语言代码 → 语言名称（用于提示词）
LANG_NAMES = {
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
}

# 批量翻译分隔标记
SEG_MARKER = "<<<SEG {n}>>>"
SEG_PATTERN = re.compile(r"<<<SEG\s+(\d+)\s*>>>")


def _glossary_prompt(glossary: dict[str, str] | None) -> str:
    """把术语表转成提示词约束。"""
    if not glossary:
        return ""
    items = "\n".join(f"- {k} -> {v}" for k, v in glossary.items())
    return (
        f" Apply this glossary strictly: always translate these terms exactly as specified "
        f"(keep the term in the target language as given):\n{items}"
    )


class OpenRouterTranslator(BaseTranslator):
    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.base_url = settings.openrouter_base_url.rstrip("/")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY 未配置")

    async def translate(self, text: str, source_lang: str, target_lang: str,
                        glossary: dict[str, str] | None = None) -> str:
        target_name = LANG_NAMES.get(target_lang, target_lang)
        source_name = LANG_NAMES.get(source_lang, source_lang) if source_lang != "auto" else "the original language"

        system_prompt = (
            f"You are a professional translator. "
            f"Translate the following text from {source_name} to {target_name}. "
            f"Return only the translation, no explanations, no quotes, no extra text. "
            f"Preserve any markdown formatting, code, and placeholders exactly."
            f"{_glossary_prompt(glossary)}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    async def translate_batch(self, texts: list[str], source_lang: str, target_lang: str,
                              glossary: dict[str, str] | None = None) -> list[str]:
        """批量翻译：多段合并为一次 LLM 调用；解析失败或数量不匹配时回退逐条。"""
        if not texts:
            return []
        if len(texts) == 1:
            return [await self.translate(texts[0], source_lang, target_lang, glossary)]

        target_name = LANG_NAMES.get(target_lang, target_lang)
        source_name = LANG_NAMES.get(source_lang, source_lang) if source_lang != "auto" else "the original language"

        joined = "\n\n".join(SEG_MARKER.format(n=i) + "\n" + t for i, t in enumerate(texts, 1))
        system_prompt = (
            f"You are a professional translator. "
            f"The user input contains multiple text segments separated by markers like '{SEG_MARKER.format(n=1)}', "
            f"where the number after SEG is the segment index. "
            f"Translate each segment from {source_name} to {target_name}. "
            f"Return ALL translated segments in the same order, each preceded by its own marker "
            f"'{SEG_MARKER.format(n=1)}' (use the same index as the input). "
            f"Do NOT merge, split, add, reorder, or drop segments. "
            f"Preserve markdown formatting, code, and placeholders exactly. "
            f"Return only the markers and translations, no explanations."
            f"{_glossary_prompt(glossary)}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": joined},
            ],
            "temperature": 0.3,
        }

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
        except Exception:
            # 请求失败：回退逐条，由调用方继续处理
            return [await self.translate(t, source_lang, target_lang) for t in texts]

        parsed = self._parse_batch_response(content, len(texts))
        if parsed is None:
            # 返回段落数不匹配：回退逐条重试
            return [await self.translate(t, source_lang, target_lang) for t in texts]
        return parsed

    @staticmethod
    def _parse_batch_response(content: str, expected: int) -> list[str] | None:
        """解析批量返回，按标记拆分；数量或编号不匹配时返回 None。"""
        matches = list(SEG_PATTERN.finditer(content))
        if not matches:
            return None
        results: dict[int, str] = {}
        for idx, m in enumerate(matches):
            num = int(m.group(1))
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            results[num] = content[start:end].strip()
        if sorted(results.keys()) != list(range(1, expected + 1)):
            return None
        return [results[i] for i in range(1, expected + 1)]
