from fastapi import FastAPI

from app.api.endpoints import files

app = FastAPI(title="OCR Processing System")

app.include_router(files.router, prefix="/api/v1", tags=["File Upload"])
