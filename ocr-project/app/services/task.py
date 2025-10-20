import logging
import uuid
from http import HTTPStatus

from sqlalchemy.orm import Session

from app.repository.task_repository import task_repo
from app.schema.task import TaskStatusResponse

logger = logging.getLogger(__name__)


class TaskServiceError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_task(
    task_id: uuid.UUID,
    db: Session,
) -> TaskStatusResponse:
    task = task_repo.get_by_id(db, task_id)
    if not task:
        raise TaskServiceError(
            message=f"Task with ID {task_id} not found.",
            status_code=HTTPStatus.NOT_FOUND,
        )

    return TaskStatusResponse(
        task_id=str(task.id),
        status=task.status.value,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
