import logging

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)

minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_USE_SSL,
)


def get_minio_client() -> Minio:
    return minio_client


def ensure_bucket_exists(bucket_name: str) -> None:
    try:
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
            logger.info("Created bucket: %s", bucket_name)
        else:
            logger.info("Bucket %s already exists", bucket_name)
    except S3Error:
        logger.exception("Error ensuring bucket exists")
        raise
