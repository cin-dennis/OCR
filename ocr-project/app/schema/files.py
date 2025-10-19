from datetime import datetime

from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    status: str
    message: str | None = None


class FileDetailResponse(BaseModel):
    id: str
    filename: str
    storage_path: str
    file_type: str
    total_pages: int
    uploaded_at: datetime | None = None


class PageResult(BaseModel):
    page_number: int
    text: str


class FileResultResponse(BaseModel):
    file_id: str
    filename: str
    status: str
    total_pages: int
    results: list[PageResult]
