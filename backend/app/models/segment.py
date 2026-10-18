"""分段模型。"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class SegmentType:
    TEXT = "text"
    CODE_BLOCK = "code_block"
    INLINE_CODE = "inline_code"
    COMMENT = "comment"
    LINK = "link"
    MENTION = "mention"


class SegmentStatus:
    PENDING = "pending"
    TRANSLATED = "translated"
    FAILED = "failed"
    MANUALLY_EDITED = "manually_edited"


class Segment(Base):
    __tablename__ = "segments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    sequence = Column(Integer, nullable=False)
    segment_type = Column(String(20), nullable=False)
    translatable = Column(Boolean, nullable=False, default=True)
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default=SegmentStatus.PENDING)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task = relationship("Task", back_populates="segments")
