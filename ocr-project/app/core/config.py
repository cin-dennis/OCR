from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/ocr_db"

    class Config:
        env_file = ".env"

settings = Settings()