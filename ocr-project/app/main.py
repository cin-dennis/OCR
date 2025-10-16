import logging

from fastapi import FastAPI

from app.api.endpoints import files, tasks

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="OCR Processing System")

app.include_router(files.router, prefix="/api/v1", tags=["File Upload"])
app.include_router(tasks.router, prefix="/api/v1", tags=["Task Status"])
