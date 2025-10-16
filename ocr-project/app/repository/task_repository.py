from sqlalchemy.orm import Session

from app.models.task import Task


class TaskRepository:
    def add(self, db: Session, task: Task) -> Task:
        db.add(task)
        db.flush()
        return task

    def get_by_id(self, db: Session, task_id: str) -> Task | None:
        return db.query(Task).filter(Task.id == task_id).first()

    def save(self, db: Session, task: Task) -> Task:
        db.add(task)
        db.flush()
        return task


task_repo = TaskRepository()
