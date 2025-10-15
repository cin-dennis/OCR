from sqlalchemy.exc import SQLAlchemyError

from app.db.session import session
from app.models.task import Task


class TaskRepository:
    def __init__(self) -> None:
        self.session = session

    def add(self, task: Task) -> None:
        try:
            self.session.add(task)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            self.session.close()

    def get_by_id(self, task_id: str) -> Task | None:
        try:
            return self.session.query(Task).filter(Task.id == task_id).first()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            self.session.close()

    def update(self, task: Task) -> None:
        try:
            self.session.merge(task)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            self.session.close()


task_repo = TaskRepository()
