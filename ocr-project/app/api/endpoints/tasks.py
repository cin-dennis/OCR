import uuid
from http import HTTPStatus

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.repository.task_repository import task_repo

router = APIRouter()


@router.get("/tasks/{task_id}/status")
def get_task_status(
    task_id: uuid.UUID,
    db: Session = Depends(get_db_session),
) -> JSONResponse:
    task = task_repo.get_by_id(db, task_id)
    if not task:
        return JSONResponse(
            status_code=HTTPStatus.NOT_FOUND,
            content={
                "code": HTTPStatus.NOT_FOUND,
                "message": f"Task with ID {task_id} not found.",
            },
        )

    return JSONResponse(
        status_code=HTTPStatus.OK,
        content={
            "task_id": str(task.id),
            "status": task.status.value,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat()
            if task.created_at
            else None,
            "updated_at": task.updated_at.isoformat()
            if task.updated_at
            else None,
        },
    )
