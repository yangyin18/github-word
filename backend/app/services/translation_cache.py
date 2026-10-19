"""翻译缓存服务：批量查询与写入，减少重复 LLM 调用。"""
import hashlib
import json

from sqlalchemy.orm import Session

from app.models.translation_cache import TranslationCache


class TranslationCacheService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _glossary_hash(glossary: dict[str, str] | None) -> str:
        """术语表指纹：术语表变化时缓存自动失效。"""
        if not glossary:
            return "none"
        raw = json.dumps(glossary, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def _key(cls, text: str, source_lang: str, target_lang: str, glossary: dict[str, str] | None = None) -> str:
        raw = f"{source_lang}|{target_lang}|{cls._glossary_hash(glossary)}|{text}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_many(self, texts: list[str], source_lang: str, target_lang: str,
                 glossary: dict[str, str] | None = None) -> dict[str, str]:
        """批量查询缓存，返回 {源文本: 译文}。"""
        if not texts:
            return {}
        key_to_text = {self._key(t, source_lang, target_lang, glossary): t for t in texts}
        rows = (
            self.db.query(TranslationCache)
            .filter(TranslationCache.id.in_(key_to_text.keys()))
            .all()
        )
        return {key_to_text[row.id]: row.translated_text for row in rows}

    def put_many(self, mapping: dict[str, str], source_lang: str, target_lang: str,
                 model: str | None = None, glossary: dict[str, str] | None = None):
        """批量写入缓存（merge 幂等，重复写入会覆盖）。"""
        if not mapping:
            return
        for text, translated in mapping.items():
            self.db.merge(TranslationCache(
                id=self._key(text, source_lang, target_lang, glossary),
                source_text=text,
                translated_text=translated,
                source_lang=source_lang,
                target_lang=target_lang,
                model=model,
            ))
        self.db.commit()
