"""分段数据访问。"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.segment import Segment, SegmentStatus


class SegmentRepo:
    def __init__(self, db: Session):
        self.db = db

    def bulk_create(self, segments: List[Segment]):
        self.db.add_all(segments)
        self.db.commit()

    def get_by_task(self, task_id: str) -> List[Segment]:
        return (
            self.db.query(Segment)
            .filter(Segment.task_id == task_id)
            .order_by(Segment.sequence)
            .all()
        )

    def get(self, segment_id: str) -> Optional[Segment]:
        return self.db.query(Segment).filter(Segment.id == segment_id).first()

    def update_translation(self, segment_id: str, translated_text: str, status: str = SegmentStatus.TRANSLATED):
        seg = self.get(segment_id)
        if seg:
            seg.translated_text = translated_text
            seg.status = status
            seg.error_message = None
            self.db.commit()
            self.db.refresh(seg)
        return seg

    def mark_failed(self, segment_id: str, error_message: str):
        seg = self.get(segment_id)
        if seg:
            seg.status = SegmentStatus.FAILED
            seg.error_message = error_message
            self.db.commit()

    def get_failed(self, task_id: str) -> List[Segment]:
        return (
            self.db.query(Segment)
            .filter(Segment.task_id == task_id, Segment.status == SegmentStatus.FAILED)
            .all()
        )
