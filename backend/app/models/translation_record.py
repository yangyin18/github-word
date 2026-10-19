"""翻译记录模型：保存每次翻译请求的原文与译文。"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Text, DateTime, BigInteger, ForeignKey

from app.database import Base


class TranslationStatus:
    COMPLETED = "completed"
    PARTIAL = "partial"      # 部分分段失败
    FAILED = "failed"


class TranslationRecord(Base):
    __tablename__ = "translation_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # 关联用户（未登录的匿名翻译为 NULL）
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)
    # 资源来源（文件 URL / issue / PR，纯文本翻译为 NULL）
    resource_url = Column(Text, nullable=True)
    source_type = Column(String(20), nullable=False, default="text")  # text / file / issue / pull_request
    source_lang = Column(String(10), nullable=False, default="auto")
    target_lang = Column(String(10), nullable=False)
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default=TranslationStatus.COMPLETED)
    error_message = Column(Text, nullable=True)
    segment_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    elapsed_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
