from fastapi import FastAPI
from app.api.endpoints import files

app = FastAPI(title="OCR Processing System")

app.include_router(files.router, prefix="/api/v1", tags=["File Upload"])

@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}
