"""术语表模型。"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime

from app.database import Base


class Glossary(Base):
    __tablename__ = "glossary"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_term = Column(String(255), nullable=False)
    target_term = Column(String(255), nullable=False)
    source_lang = Column(String(10), nullable=False)
    target_lang = Column(String(10), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
