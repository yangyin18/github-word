"""任务数据访问。"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.task import Task, TaskStatus


class TaskRepo:
    def __init__(self, db: Session):
        self.db = db

    def create(self, task: Task) -> Task:
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get(self, task_id: str) -> Optional[Task]:
        return self.db.query(Task).filter(Task.id == task_id).first()

    def update_status(self, task_id: str, status: str, error_message: str = None):
        task = self.get(task_id)
        if task:
            task.status = status
            if error_message is not None:
                task.error_message = error_message
            self.db.commit()

    def update_source_content(self, task_id: str, content: str):
        task = self.get(task_id)
        if task:
            task.source_content = content
            self.db.commit()

    def update_progress(self, task_id: str, translated_count: int, total_count: int):
        """更新翻译阶段实时进度。"""
        task = self.get(task_id)
        if task:
            task.translated_count = translated_count
            task.total_count = total_count
            self.db.commit()
