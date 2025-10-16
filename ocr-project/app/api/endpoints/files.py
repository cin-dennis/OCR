import os
import uuid
from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from minio.error import S3Error
from sqlalchemy.exc import SQLAlchemyError

from app.models.file import File as FileModel
from app.models.task import TaskStatus
from app.repository.file_repository import file_repo
from app.services.file.file_service import FileService
from app.storage.file_storage import FileStorage
from app.type.error import ErrorResponse
from app.worker.file_process_worker import process_file

BUCKET_NAME = os.environ.get("BUCKET_NAME", "files")
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg"}

file_service = FileService(BUCKET_NAME, ALLOWED_CONTENT_TYPES)
file_storage = FileStorage(BUCKET_NAME)


router = APIRouter()


@router.post("/files", status_code=HTTPStatus.ACCEPTED)
async def upload_file(file: UploadFile = File(...)) -> JSONResponse:
    if not file_service.is_allowed_file_type(file.content_type):
        return JSONResponse(
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            content=ErrorResponse(
                code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                message=f"File type '{file.content_type}' is not allowed."
                f" Please upload a PDF, PNG, or JPG.",
            ),
        )

    task_id = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix
    storage_path = f"{task_id}-{file.filename}-{file_extension}"

    try:
        await file_storage.upload_file(file, storage_path, BUCKET_NAME)
    except S3Error as e:
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message=f"Failed to upload file to storage: {e}",
            ),
        )

    file_model = FileModel(
        filename=file.filename,
        storage_path=storage_path,
        file_type=file.content_type,
    )

    try:
        file_repo.save(file_model)
    except SQLAlchemyError as e:
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message=f"Failed to save file metadata to database: {e}",
            ),
        )

    process_file.delay(str(file_model.id))

    return JSONResponse(
        status_code=HTTPStatus.CREATED,
        content={
            "message": "File upload accepted and is being processed.",
            "task_id": task_id,
            "filename": file.filename,
            "status": TaskStatus.PENDING,
        },
    )
