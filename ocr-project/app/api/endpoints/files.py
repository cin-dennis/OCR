import os
import uuid
from http import HTTPStatus
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from minio.error import S3Error
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import session
from app.models.file import File as FileModel
from app.models.task import TaskStatus
from app.services.minio import minio_service
from app.type.error import ErrorResponse

ALLOWED_CONTENT_TYPES = ["application/pdf", "image/png", "image/jpeg"]
BUCKET_NAME = os.environ.get("BUCKET_NAME", "files")

router = APIRouter()


@router.post("/files", status_code=HTTPStatus.ACCEPTED)
async def upload_file(file: UploadFile = File(...)) -> JSONResponse:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        return JSONResponse(
            status_code=415,
            content=ErrorResponse(
                code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                message=f"File type '{file.content_type}' is not allowed."
                f" Please upload a PDF, PNG, or JPG.",
            ),
        )

    task_id = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix
    storage_path = f"{task_id}-{file.filename}-{file_extension}"

    file_data = await file.read()
    file_bytes_io = BytesIO(file_data)

    try:
        minio_service.get_minio_client().put_object(
            BUCKET_NAME,
            storage_path,
            data=file_bytes_io,
            length=len(file_data),
            content_type=file.content_type,
        )
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
        session.add(file_model)
        session.commit()
    except SQLAlchemyError as e:
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code=HTTPStatus.INTERNAL_SERVER_ERROR,
                message=f"Failed to save file metadata to database: {e}",
            ),
        )
    finally:
        session.close()

    return JSONResponse(
        status_code=HTTPStatus.CREATED,
        content={
            "message": "File upload accepted and is being processed.",
            "task_id": task_id,
            "filename": file.filename,
            "status": TaskStatus.PENDING,
        },
    )
