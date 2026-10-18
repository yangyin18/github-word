"""分段相关的请求/响应模型。"""
from typing import Optional, List
from pydantic import BaseModel


class SegmentResponse(BaseModel):
    segment_id: str
    sequence: int
    segment_type: str
    translatable: bool
    source_text: str
    translated_text: Optional[str] = None
    status: str
    error_message: Optional[str] = None


class SegmentListResponse(BaseModel):
    segments: List[SegmentResponse]


class SegmentUpdateRequest(BaseModel):
    translated_text: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: Optional[str] = None
    retry_after: Optional[int] = None
