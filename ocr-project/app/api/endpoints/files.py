import logging
import uuid
from http import HTTPStatus
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.schema.common import ErrorResponse

if TYPE_CHECKING:
    from app.schema.files import (
        FileDetailResponse,
        FileResultResponse,
        FileUploadResponse,
    )
from app.services.file_service import (
    FileServiceError,
    get_file,
    get_results,
    handle_file_upload,
)

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg"}

router = APIRouter()


@router.post("/files", status_code=HTTPStatus.CREATED)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
) -> JSONResponse:
    try:
        result: FileUploadResponse = await handle_file_upload(file, db)
        return JSONResponse(
            status_code=HTTPStatus.CREATED,
            content=result.model_dump(),
        )

    except FileServiceError as e:
        return JSONResponse(
            status_code=e.status_code,
            content=ErrorResponse(
                code=e.status_code,
                message=e.message,
            ).model_dump(),
        )

    except Exception:
        logger.exception("Unexpected server error during file upload")
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message="Internal server error during file upload.",
            ).model_dump(),
        )


@router.get("/files/{file_id}")
def get_file_details(
    file_id: uuid.UUID,
    db: Session = Depends(get_db_session),
) -> JSONResponse:
    try:
        file: FileDetailResponse = get_file(file_id, db)
        return JSONResponse(
            status_code=HTTPStatus.OK,
            content=file.model_dump(mode="json"),
        )
    except FileServiceError as e:
        logger.exception("Error retrieving file details")
        return JSONResponse(
            status_code=e.status_code,
            content=ErrorResponse(
                code=e.status_code,
                message=e.message,
            ).model_dump(),
        )
    except Exception:
        logger.exception(
            "Unexpected server error during file detail retrieval",
        )
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message="Internal server error during file detail retrieval.",
            ).model_dump(),
        )


@router.get("/files/{file_id}/result")
def get_file_result(
    file_id: uuid.UUID,
    db: Session = Depends(get_db_session),
) -> JSONResponse:
    try:
        result: FileResultResponse = get_results(file_id, db)
        return JSONResponse(
            status_code=HTTPStatus.OK,
            content=result.model_dump(),
        )
    except FileServiceError as e:
        logger.warning("Error retrieving file result")
        return JSONResponse(
            status_code=e.status_code,
            content=ErrorResponse(
                code=e.status_code,
                message=e.message,
            ).model_dump(),
        )
    except Exception:
        logger.exception(
            "Unexpected server error during file result retrieval",
        )
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message="Internal server error during file result retrieval.",
            ).model_dump(),
        )
