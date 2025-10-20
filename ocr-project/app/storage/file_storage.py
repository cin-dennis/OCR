import logging
from io import BytesIO

from fastapi import UploadFile
from minio import Minio, S3Error

from app.helper.minio.minio import (
    ensure_bucket_exists,
)

logger = logging.getLogger(__name__)


class FileStorage:
    def __init__(self, minio_client: Minio) -> None:
        self.minio_client = minio_client

    async def upload_file(
        self,
        file: UploadFile,
        storage_path: str,
        bucket_name: str,
    ) -> None:
        ensure_bucket_exists(bucket_name)
        data = await file.read()
        try:
            self.minio_client.put_object(
                bucket_name,
                storage_path,
                data=BytesIO(data),
                length=len(data),
                content_type=file.content_type,
            )
        except S3Error:
            logger.exception("Failed to upload file to MinIO")
            raise
