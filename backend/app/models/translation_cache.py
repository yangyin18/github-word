"""翻译缓存模型：同源文本+语言对命中时直接复用译文。"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime

from app.database import Base


class TranslationCache(Base):
    __tablename__ = "translation_cache"

    # sha256(f"{source_lang}|{target_lang}|{source_text}") 十六进制
    id = Column(String(64), primary_key=True)
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)
    source_lang = Column(String(10), nullable=False)
    target_lang = Column(String(10), nullable=False)
    model = Column(String(100), nullable=True)  # 产生译文时使用的模型（便于排查）
    created_at = Column(DateTime, default=datetime.utcnow)
