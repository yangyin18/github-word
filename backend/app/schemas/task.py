"""任务相关的请求/响应模型。"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl


class TaskCreateRequest(BaseModel):
    resource_url: str
    target_lang: str
    source_lang: str = "auto"


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str
    resource_type: str


class TaskResponse(BaseModel):
    task_id: str
    status: str
    resource_type: str
    resource_url: str
    source_lang: str
    target_lang: str
    total_segments: int = 0
    translated_segments: int = 0
    failed_segments: int = 0
    # 翻译阶段实时进度（旧任务可能为 NULL）
    translated_count: Optional[int] = None
    total_count: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TranslationResultResponse(BaseModel):
    translated_markdown: str


class RetryResponse(BaseModel):
    retried_count: int
    status: str
