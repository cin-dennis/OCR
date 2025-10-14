import uuid

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

ALLOWED_CONTENT_TYPES = ["application/pdf", "image/png", "image/jpeg"]

router = APIRouter()

@router.post("/upload", status_code=202)
async def upload_file(
        file: UploadFile = File(...)
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        error_response = {
            "code": "unsupported_media_type",
            "message": f"File type '{file.content_type}' is not allowed. Please upload a PDF, PNG, or JPG.",
        }
        return JSONResponse(status_code=415, content=error_response)

    task_id = str(uuid.uuid4())

    return {
        "message": "File upload accepted and is being processed.",
        "task_id": task_id,
        "filename": file.filename,
        "status": "processing"
    }