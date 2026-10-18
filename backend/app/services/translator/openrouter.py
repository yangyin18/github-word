"""OpenRouter 翻译实现：通过 OpenAI 兼容接口调用大模型翻译。"""
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


class OpenRouterTranslator(BaseTranslator):
    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.base_url = settings.openrouter_base_url.rstrip("/")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY 未配置")

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        target_name = LANG_NAMES.get(target_lang, target_lang)
        source_name = LANG_NAMES.get(source_lang, source_lang) if source_lang != "auto" else "the original language"

        system_prompt = (
            f"You are a professional translator. "
            f"Translate the following text from {source_name} to {target_name}. "
            f"Return only the translation, no explanations, no quotes, no extra text. "
            f"Preserve any markdown formatting, code, and placeholders exactly."
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
