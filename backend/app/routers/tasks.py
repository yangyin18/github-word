"""任务相关路由。"""
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.task import (
    TaskCreateRequest, TaskCreateResponse, TaskResponse,
    TranslationResultResponse, RetryResponse,
)
from app.schemas.segment import SegmentListResponse, SegmentUpdateRequest, SegmentResponse
from app.services.task_service import TaskService
from app.config import SUPPORTED_LANGUAGES
from app.utils.errors import AppError

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskCreateResponse, status_code=201)
def create_task(req: TaskCreateRequest, bg: BackgroundTasks, db: Session = Depends(get_db)):
    # 校验目标语言
    if req.target_lang not in [l["code"] for l in SUPPORTED_LANGUAGES]:
        raise AppError(
            error="unsupported_language",
            message=f"不支持的目标语言: {req.target_lang}",
            detail=f"支持的语言: {', '.join(l['code'] for l in SUPPORTED_LANGUAGES)}",
            status_code=400,
        )

    service = TaskService(db)
    try:
        task = service.create_task(req.resource_url, req.target_lang, req.source_lang)
    except ValueError as e:
        raise AppError(error="invalid_resource", message=str(e), status_code=400)

    # 异步执行翻译流程
    bg.add_task(service.process_task, task.id)

    return TaskCreateResponse(task_id=task.id, status=task.status, resource_type=task.resource_type)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    service = TaskService(db)
    result = service.get_task_with_stats(task_id)
    if not result:
        raise AppError(error="not_found", message="任务不存在", status_code=404)
    task, total, translated, failed = result
    return TaskResponse(
        task_id=task.id,
        status=task.status,
        resource_type=task.resource_type,
        resource_url=task.resource_url,
        source_lang=task.source_lang,
        target_lang=task.target_lang,
        total_segments=total,
        translated_segments=translated,
        failed_segments=failed,
        translated_count=task.translated_count,
        total_count=task.total_count,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("/{task_id}/segments", response_model=SegmentListResponse)
def get_segments(task_id: str, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.task_repo.get(task_id)
    if not task:
        raise AppError(error="not_found", message="任务不存在", status_code=404)
    segments = service.segment_repo.get_by_task(task_id)
    return SegmentListResponse(segments=[
        SegmentResponse(
            segment_id=s.id,
            sequence=s.sequence,
            segment_type=s.segment_type,
            translatable=s.translatable,
            source_text=s.source_text,
            translated_text=s.translated_text,
            status=s.status,
            error_message=s.error_message,
        ) for s in segments
    ])


@router.get("/{task_id}/result", response_model=TranslationResultResponse)
def get_result(task_id: str, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.task_repo.get(task_id)
    if not task:
        raise AppError(error="not_found", message="任务不存在", status_code=404)
    md = service.assemble_result(task_id)
    return TranslationResultResponse(translated_markdown=md)


@router.put("/{task_id}/segments/{segment_id}", response_model=SegmentResponse)
def update_segment(task_id: str, segment_id: str, req: SegmentUpdateRequest, db: Session = Depends(get_db)):
    service = TaskService(db)
    seg = service.segment_repo.get(segment_id)
    if not seg or seg.task_id != task_id:
        raise AppError(error="not_found", message="分段不存在", status_code=404)
    updated = service.segment_repo.update_translation(
        segment_id, req.translated_text, status="manually_edited"
    )
    return SegmentResponse(
        segment_id=updated.id,
        sequence=updated.sequence,
        segment_type=updated.segment_type,
        translatable=updated.translatable,
        source_text=updated.source_text,
        translated_text=updated.translated_text,
        status=updated.status,
        error_message=updated.error_message,
    )


@router.post("/{task_id}/retry", response_model=RetryResponse)
async def retry_task(task_id: str, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.task_repo.get(task_id)
    if not task:
        raise AppError(error="not_found", message="任务不存在", status_code=404)
    count = await service.retry_failed(task_id)
    return RetryResponse(retried_count=count, status=task.status)
