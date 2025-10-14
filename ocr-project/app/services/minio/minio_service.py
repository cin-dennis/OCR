from minio import Minio
from app.core.config import settings

minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_USE_SSL
)

def get_minio_client() -> Minio:
    return minio_client

def ensure_bucket_exists(client: Minio, bucket_name: str):
    try:
        found = client.bucket_exists(bucket_name)
        if not found:
            client.make_bucket(bucket_name)
            print(f"Successfully created bucket: '{bucket_name}'")
        else:
            print(f"Bucket '{bucket_name}' already exists.")
    except Exception as e:
        print(f"Error checking or creating bucket: {e}")
        raise