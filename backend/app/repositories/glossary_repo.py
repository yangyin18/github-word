"""术语表数据访问。"""
from typing import List
from sqlalchemy.orm import Session
from app.models.glossary import Glossary


class GlossaryRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_by_lang_pair(self, source_lang: str, target_lang: str) -> List[Glossary]:
        return (
            self.db.query(Glossary)
            .filter(Glossary.source_lang == source_lang, Glossary.target_lang == target_lang)
            .all()
        )

    def create(self, glossary: Glossary) -> Glossary:
        self.db.add(glossary)
        self.db.commit()
        self.db.refresh(glossary)
        return glossary

    def delete(self, glossary_id: str) -> bool:
        g = self.db.query(Glossary).filter(Glossary.id == glossary_id).first()
        if g:
            self.db.delete(g)
            self.db.commit()
            return True
        return False
