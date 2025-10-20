import logging
import uuid
from http import HTTPStatus
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.schema.common import ErrorResponse

if TYPE_CHECKING:
    from app.schema.task import TaskStatusResponse
from app.services.task import TaskServiceError, get_task

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/tasks/{task_id}/status")
def get_task_status(
    task_id: uuid.UUID,
    db: Session = Depends(get_db_session),
) -> JSONResponse:
    try:
        task: TaskStatusResponse = get_task(task_id, db)
        return JSONResponse(
            status_code=HTTPStatus.OK,
            content=task.model_dump(mode="json"),
        )
    except TaskServiceError as e:
        return JSONResponse(
            status_code=e.status_code,
            content=ErrorResponse(
                code=e.status_code,
                message=e.message,
            ).model_dump(),
        )
    except Exception:
        logger.exception(
            "Internal server error while retrieving task status",
        )
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message="Internal server error while retrieving task status.",
            ).model_dump(),
        )
