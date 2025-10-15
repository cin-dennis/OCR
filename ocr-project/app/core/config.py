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

    # RABBITMQ settings
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "dennis"
    RABBITMQ_PASSWORD: str = "tojidev"

    # REDIS settings
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    model_config = {
        "env_file": BASE_DIR / ".env",
        "extra": "ignore",
    }

    def get_database_url(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:"
            f"{self.POSTGRES_PORT}/"
            f"{self.POSTGRES_DB}"
        )


settings = Settings()
