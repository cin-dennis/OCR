import logging
from io import BytesIO

from minio import Minio, S3Error

logger = logging.getLogger(__name__)

ENCODING_FORMAT = "utf-8"


class ResultStorage:
    def __init__(self, minio_client: Minio) -> None:
        self.minio_client = minio_client

    async def upload_result(
        self,
        result_data: str,
        storage_path: str,
        bucket_name: str,
    ) -> None:
        try:
            self.minio_client.put_object(
                bucket_name,
                storage_path,
                data=BytesIO(result_data.encode(ENCODING_FORMAT)),
                length=len(result_data),
                content_type="application/json",
            )
        except S3Error:
            logger.exception("Failed to upload result to MinIO")
            raise
