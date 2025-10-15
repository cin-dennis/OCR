import os
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from minio.error import S3Error

from app.services.minio import minio_service

ALLOWED_CONTENT_TYPES = ["application/pdf", "image/png", "image/jpeg"]
BUCKET_NAME = os.environ.get("BUCKET_NAME", "files")

router = APIRouter()


@router.post("/files", status_code=202)
async def upload_file(file: UploadFile = File(...)) -> JSONResponse:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        error_response = {
            "code": "unsupported_media_type",
            "message": f"File type '{file.content_type}' is not allowed."
            f" Please upload a PDF, PNG, or JPG.",
        }
        return JSONResponse(status_code=415, content=error_response)

    task_id = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix
    storage_path = f"{task_id}{file_extension}"

    try:
        file_data = await file.read()
        file_bytes_io = BytesIO(file_data)
        minio_service.get_minio_client().put_object(
            BUCKET_NAME,
            storage_path,
            data=file_bytes_io,
            length=len(file_data),
            content_type=file.content_type,
        )
    except S3Error as e:
        return JSONResponse(
            status_code=500,
            content={"code": "upload_failed", "message": str(e)},
        )

    return {
        "message": "File upload accepted and is being processed.",
        "task_id": task_id,
        "filename": file.filename,
        "status": "processing",
    }
