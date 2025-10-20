import json
import logging
import uuid
from http import HTTPStatus
from pathlib import Path

from celery.exceptions import CeleryError
from fastapi import UploadFile
from minio.error import S3Error
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.constant.constant import BUCKET_FILE_STORAGE, BUCKET_RESULT_STORAGE
from app.helper.file.file_helper import FileHelper
from app.helper.minio.minio import get_minio_client
from app.models.file import File as FileModel
from app.models.task import Task, TaskStatus
from app.repository.file_repository import file_repo
from app.repository.task_repository import task_repo
from app.schema.files import (
    FileDetailResponse,
    FileResultResponse,
    FileUploadResponse,
    PageResult,
)
from app.storage.file_storage import FileStorage
from app.worker.file_process_worker import process_file

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg"}

file_service = FileHelper(BUCKET_FILE_STORAGE, ALLOWED_CONTENT_TYPES)
file_storage = FileStorage(get_minio_client())


class FileServiceError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def handle_file_upload(
    file: UploadFile,
    db: Session,
) -> FileUploadResponse:
    # Check file type
    if not file_service.is_allowed_file_type(file.content_type):
        raise FileServiceError(
            message=(
                f"File type '{file.content_type}' is not allowed. "
                f"Please upload a PDF, PNG, or JPG."
            ),
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        )

    file_id = uuid.uuid4()
    file_extension = Path(file.filename).suffix
    storage_path = f"{file_id!s}{file_extension}"

    # Upload to storage
    try:
        await file_storage.upload_file(file, storage_path, BUCKET_FILE_STORAGE)
    except S3Error as e:
        raise FileServiceError(
            message="Error while upload file to storage",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        ) from e
    except Exception:
        logger.exception("Failed to upload file to storage")
        raise

    # Save DB, create task, push task
    try:
        file_model = FileModel(
            id=file_id,
            filename=file.filename,
            storage_path=storage_path,
            file_type=file.content_type,
        )
        saved_file = file_repo.add(db, file_model)

        task_model = Task(file_id=saved_file.id, status=TaskStatus.PENDING)
        saved_task = task_repo.add(db, task_model)

        process_file.delay(str(saved_task.id))

        db.commit()
        db.refresh(saved_task)

    except SQLAlchemyError as e:
        db.rollback()
        logger.exception("Database or Celery error while handling upload")
        get_minio_client().remove_object(BUCKET_FILE_STORAGE, storage_path)
        raise FileServiceError(
            message="Failed to store file metadata or queue processing task.",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        ) from e
    except CeleryError as e:
        db.rollback()
        logger.exception("Failed to enqueue file processing task")
        get_minio_client().remove_object(BUCKET_FILE_STORAGE, storage_path)
        raise FileServiceError(
            message="Failed to enqueue file processing task.",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        ) from e

    except Exception:
        db.rollback()
        logger.exception("Unexpected error while saving file or task")
        get_minio_client().remove_object(BUCKET_FILE_STORAGE, storage_path)
        raise

    return FileUploadResponse(
        id=str(saved_file.id),
        filename=saved_file.filename,
        file_type=saved_file.file_type,
        status=saved_task.status.value,
    )


def get_file(file_id: uuid.UUID, db: Session) -> FileDetailResponse:
    file = file_repo.get_by_id(db, file_id)
    if not file:
        raise FileServiceError(
            message=f"File with ID {file_id} not found.",
            status_code=HTTPStatus.NOT_FOUND,
        )

    return FileDetailResponse(
        id=str(file.id),
        filename=file.filename,
        storage_path=file.storage_path,
        file_type=file.file_type,
        total_pages=file.total_pages,
        uploaded_at=file.uploaded_at,
    )


def get_results(file_id: uuid.UUID, db: Session) -> FileResultResponse:
    file = file_repo.get_by_id(db, file_id)
    if not file or not file.task:
        raise FileServiceError(
            message=f"File with ID {file_id} not found.",
            status_code=HTTPStatus.NOT_FOUND,
        )

    task = file.task
    if task.status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
        return FileResultResponse(
            file_id=str(file.id),
            filename=file.filename,
            status=str(task.status.value),
            total_pages=file.total_pages,
            results=[],
        )

    if task.status == TaskStatus.FAILED:
        raise FileServiceError(
            message=f"File processing failed: {task.error_message}",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
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
    except S3Error as e:
        raise FileServiceError(
            message="Failed to retrieve result from storage.",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        ) from e
    except json.JSONDecodeError as e:
        raise FileServiceError(
            message="Malformed JSON in result data.",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        ) from e
    except Exception:
        raise

    return FileResultResponse(
        file_id=str(file.id),
        filename=file.filename,
        status=task.status.value,
        total_pages=file.total_pages,
        results=page_results,
    )
