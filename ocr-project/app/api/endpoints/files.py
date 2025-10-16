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

from app.constant.constant import BUCKET_FILE_STORAGE
from app.db.dependencies import get_db_session
from app.models.file import File as FileModel
from app.models.task import Task, TaskStatus
from app.repository.file_repository import file_repo
from app.repository.task_repository import task_repo
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
            content={
                "code": HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "message": f"File type '{file.content_type}' is not allowed."
                f" Please upload a PDF, PNG, or JPG.",
            },
        )

    file_id = uuid.uuid4()
    file_extension = Path(file.filename).suffix
    storage_path = f"{file_id!s}{file_extension}"

    try:
        await file_storage.upload_file(file, storage_path, BUCKET_FILE_STORAGE)
    except S3Error as e:
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={
                "code": HTTPStatus.INTERNAL_SERVER_ERROR,
                "message": f"Failed to upload file to storage: {e}",
            },
        )

    file_model = FileModel(
        id=file_id,
        filename=file.filename,
        storage_path=storage_path,
        file_type=file.content_type,
    )

    try:
        saved_file = file_repo.add(db, file_model)

        task_model = Task(
            file_id=saved_file.id,
            status=TaskStatus.PENDING,
        )
        saved_task = task_repo.add(db, task_model)

        process_file.delay(saved_task.id)

        db.commit()
        db.refresh(saved_task)
    except SQLAlchemyError as e:
        db.rollback()
        logger.exception(
            "Failed to save file metadata or task to database",
        )
        get_minio_client().remove_object(BUCKET_FILE_STORAGE, storage_path)
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={
                "code": HTTPStatus.INTERNAL_SERVER_ERROR,
                "message": f"Failed to save file metadata to database: {e}",
            },
        )
    except CeleryError as e:
        db.rollback()
        logger.exception(
            "Failed to queue task for file %s",
            saved_file.id,
        )
        get_minio_client().remove_object(BUCKET_FILE_STORAGE, storage_path)
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={
                "code": HTTPStatus.INTERNAL_SERVER_ERROR,
                "message": f"Failed to queue file processing task: {e}",
            },
        )
    except Exception:
        db.rollback()
        logger.exception("Failed to save file metadata to database")
        get_minio_client().remove_object(BUCKET_FILE_STORAGE, storage_path)
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={
                "code": HTTPStatus.INTERNAL_SERVER_ERROR,
                "message": "Server error occurred while processing the file.",
            },
        )

    return JSONResponse(
        status_code=HTTPStatus.CREATED,
        content={
            "message": "File upload accepted and is being processed.",
            "task_id": str(saved_task.id),
            "filename": file.filename,
            "status": TaskStatus.PENDING.value,
        },
    )
