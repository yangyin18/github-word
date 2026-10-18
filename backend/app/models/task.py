"""翻译任务模型。"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.orm import relationship

from app.database import Base


class TaskStatus:
    CREATED = "created"
    FETCHING = "fetching"
    FETCHED = "fetched"
    PARSING = "parsing"
    TRANSLATING = "translating"
    COMPLETED = "completed"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"


class ResourceType:
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    README = "readme"
    REPO_META = "repo_meta"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resource_type = Column(String(20), nullable=False)
    resource_url = Column(Text, nullable=False)
    repo_full_name = Column(String(255), nullable=False)
    resource_number = Column(Integer, nullable=True)
    source_lang = Column(String(10), nullable=False, default="auto")
    target_lang = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, default=TaskStatus.CREATED)
    source_content = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    segments = relationship("Segment", back_populates="task", cascade="all, delete-orphan")
