"""术语表后处理服务。"""
import re
from sqlalchemy.orm import Session
from app.repositories.glossary_repo import GlossaryRepo


class GlossaryService:
    def __init__(self, db: Session):
        self.repo = GlossaryRepo(db)

    def apply(self, translated_text: str, source_lang: str, target_lang: str) -> str:
        """对译文做术语一致性校正：把译文中残留的源术语替换为目标术语。"""
        terms = self.repo.get_by_lang_pair(source_lang, target_lang)
        if not terms:
            return translated_text

        # 过滤无效条目，按源术语长度降序（最长匹配优先）
        valid = [t for t in terms if t.source_term and t.target_term]
        valid.sort(key=lambda t: len(t.source_term), reverse=True)

        result = translated_text
        for term in valid:
            # 单词边界匹配源术语（忽略大小写），避免词内误替换
            pattern = re.compile(r"\b" + re.escape(term.source_term) + r"\b", re.IGNORECASE)
            result = pattern.sub(term.target_term, result)

        return result

    def get_terms_dict(self, source_lang: str, target_lang: str) -> dict[str, str]:
        """返回 {源术语: 目标术语}，用于注入翻译提示词。"""
        terms = self.repo.get_by_lang_pair(source_lang, target_lang)
        return {t.source_term: t.target_term for t in terms if t.source_term and t.target_term}
