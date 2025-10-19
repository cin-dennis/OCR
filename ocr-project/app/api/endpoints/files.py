import json
import logging
import uuid
from http import HTTPStatus
from pathlib import Path

from celery.exceptions import CeleryError
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from minio.error import S3Error
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.constant.constant import (
    BUCKET_FILE_STORAGE,
    BUCKET_RESULT_STORAGE,
)
from app.db.dependencies import get_db_session
from app.models.file import File as FileModel
from app.models.task import Task, TaskStatus
from app.repository.file_repository import file_repo
from app.repository.task_repository import task_repo
from app.schema.common import ErrorResponse
from app.schema.files import (
    FileDetailResponse,
    FileResultResponse,
    FileUploadResponse,
    PageResult,
)
from app.services.file.file_service import FileService
from app.services.minio.minio_service import get_minio_client
from app.storage.file_storage import FileStorage
from app.worker.file_process_worker import process_file

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg"}

file_service = FileService(BUCKET_FILE_STORAGE, ALLOWED_CONTENT_TYPES)
file_storage = FileStorage(get_minio_client())

router = APIRouter()


@router.post("/files", status_code=HTTPStatus.CREATED)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
) -> JSONResponse:
    if not file_service.is_allowed_file_type(file.content_type):
        return JSONResponse(
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            content=ErrorResponse(
                code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                message=f"File type '{file.content_type}' is not allowed."
                f" Please upload a PDF, PNG, or JPG.",
            ).model_dump(),
        )

    file_id = uuid.uuid4()
    file_extension = Path(file.filename).suffix
    storage_path = f"{file_id!s}{file_extension}"

    try:
        await file_storage.upload_file(file, storage_path, BUCKET_FILE_STORAGE)
    except S3Error:
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message="Failed to upload file to storage",
            ).model_dump(),
        )

    try:
        file_model = FileModel(
            id=file_id,
            filename=file.filename,
            storage_path=storage_path,
            file_type=file.content_type,
        )

        saved_file = file_repo.add(db, file_model)

        task_model = Task(
            file_id=saved_file.id,
            status=TaskStatus.PENDING,
        )
        saved_task = task_repo.add(db, task_model)

        process_file.delay(str(saved_task.id))

        db.commit()
        db.refresh(saved_task)
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Failed to save file metadata or task to database",
        )
        get_minio_client().remove_object(BUCKET_FILE_STORAGE, storage_path)
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message="Failed to save file metadata to database.",
            ).model_dump(),
        )
    except CeleryError:
        db.rollback()
        logger.exception(
            "Failed to queue task for file",
        )
        get_minio_client().remove_object(BUCKET_FILE_STORAGE, storage_path)
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message="Failed to queue file processing task.",
            ).model_dump(),
        )
    except Exception:
        db.rollback()
        logger.exception("Failed to process file")
        get_minio_client().remove_object(BUCKET_FILE_STORAGE, storage_path)
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message="Server error occurred while processing the file.",
            ).model_dump(),
        )

    return JSONResponse(
        status_code=HTTPStatus.CREATED,
        content=FileUploadResponse(
            id=str(saved_file.id),
            filename=saved_file.filename,
            file_type=saved_file.file_type,
            status=saved_task.status.value,
        ).model_dump(),
    )


@router.get("/files/{file_id}")
def get_file_details(
    file_id: uuid.UUID,
    db: Session = Depends(get_db_session),
) -> JSONResponse:
    file = file_repo.get_by_id(db, file_id)
    if not file:
        return JSONResponse(
            status_code=HTTPStatus.NOT_FOUND,
            content=ErrorResponse(
                code=HTTPStatus.NOT_FOUND,
                message=f"File with ID {file_id} not found.",
            ).model_dump(),
        )

    return JSONResponse(
        status_code=HTTPStatus.OK,
        content=FileDetailResponse(
            id=str(file.id),
            filename=file.filename,
            storage_path=file.storage_path,
            file_type=file.file_type,
            total_pages=file.total_pages,
            uploaded_at=file.uploaded_at,
        ).model_dump(),
    )


@router.get("/files/{file_id}/result")
def get_file_result(
    file_id: uuid.UUID,
    db: Session = Depends(get_db_session),
) -> JSONResponse:
    file = file_repo.get_by_id(db, file_id)
    if not file or not file.task:
        return JSONResponse(
            status_code=HTTPStatus.NOT_FOUND,
            content=ErrorResponse(
                code=HTTPStatus.NOT_FOUND,
                message=f"File with ID {file_id} not found.",
            ).model_dump(),
        )

    task = file.task
    if task.status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
        return JSONResponse(
            status_code=HTTPStatus.ACCEPTED,
            content=FileResultResponse(
                file_id=str(file.id),
                filename=file.filename,
                status=str(task.status.value),
                total_pages=file.total_pages,
                results=[],
            ).model_dump(),
        )

    if task.status == TaskStatus.FAILED:
        return JSONResponse(
            status_code=HTTPStatus.OK,
            content=FileResultResponse(
                file_id=str(file.id),
                filename=file.filename,
                status=task.status.value,
                total_pages=file.total_pages,
                results=[],
            ).model_dump(),
        )

    page_results = []
    minio_client = get_minio_client()

    sorted_pages = sorted(file.page_results, key=lambda p: p.page_number)

    try:
        for page in sorted_pages:
            result_object = minio_client.get_object(
                BUCKET_RESULT_STORAGE,
                page.result_path,
            )

            result_data = json.loads(result_object.read().decode("utf-8"))

            page_results.append(
                PageResult(
                    page_number=page.page_number,
                    text=result_data.get("text", ""),
                ),
            )
    except S3Error:
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message="Failed to retrieve result from storage.",
            ).model_dump(),
        )
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message="Malformed JSON in result data.",
            ).model_dump(),
        )
    except Exception:
        logger.exception("Failed to retrieve or parse file results")
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message="Server error occurred while retrieving file results.",
            ).model_dump(),
        )

    return JSONResponse(
        status_code=HTTPStatus.OK,
        content=FileResultResponse(
            file_id=str(file.id),
            filename=file.filename,
            status=task.status.value,
            total_pages=file.total_pages,
            results=page_results,
        ).model_dump(),
    )
