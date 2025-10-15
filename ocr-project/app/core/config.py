from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # Database settings
    POSTGRES_DB: str = "ocr_db"
    POSTGRES_USER: str = "dennis"
    POSTGRES_PASSWORD: str = "tojidev"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # MinIO settings
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "ocr-files"
    MINIO_USE_SSL: bool = False

    model_config = {
        "env_file": BASE_DIR / ".env",
        "extra": "ignore",
    }


settings = Settings()
