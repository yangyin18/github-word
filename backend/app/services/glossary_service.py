"""术语表后处理服务。"""
import re
from sqlalchemy.orm import Session
from app.repositories.glossary_repo import GlossaryRepo


class GlossaryService:
    def __init__(self, db: Session):
        self.repo = GlossaryRepo(db)

    def apply(self, translated_text: str, source_lang: str, target_lang: str) -> str:
        """对译文做术语一致性校正：单词边界安全 + 最长匹配。"""
        terms = self.repo.get_by_lang_pair(source_lang, target_lang)
        if not terms:
            return translated_text

        # 按目标术语长度降序（最长匹配优先）
        terms.sort(key=lambda t: len(t.target_term), reverse=True)

        result = translated_text
        for term in terms:
            # 单词边界匹配，避免词内替换
            pattern = re.compile(r"\b" + re.escape(term.target_term) + r"\b")
            result = pattern.sub(term.target_term, result)

        return result
