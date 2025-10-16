import json
import logging
import uuid
from io import BytesIO
from typing import Any

import requests
from minio.error import S3Error
from pdf2image import convert_from_bytes
from sqlalchemy.orm import Session

from app.constant.constant import (
    AI_SERVICE_URL,
    BUCKET_FILE_STORAGE,
    BUCKET_RESULT_STORAGE,
)
from app.db.session import SessionLocal
from app.models import File, PageResult, Task
from app.models.task import TaskStatus
from app.repository.file_repository import file_repo
from app.repository.page_result_repository import page_result_repo
from app.repository.task_repository import task_repo
from app.services.minio.minio_service import get_minio_client
from app.storage.result_storage import ResultStorage

from .celery import celery_app

logger = logging.getLogger(__name__)


def get_validated_task_and_file(
    db: Session,
    task_id: uuid.UUID,
) -> tuple[Task, File]:
    task = task_repo.get_by_id(db, task_id)
    if not task:
        raise ValueError(f"Task with ID {task_id} not found.")

    file = file_repo.get_by_id(db, task.file_id)
    if not file:
        raise ValueError(
            f"File with ID {task.file_id} not found for task {task_id}.",
        )

    return task, file


def download_file_from_minio(file_storage_path: str) -> bytes:
    try:
        minio_client = get_minio_client()
        file_object = minio_client.get_object(
            BUCKET_FILE_STORAGE,
            file_storage_path,
        )
        return file_object.read()
    except S3Error as e:
        logger.exception("Failed to retrieve file from MinIO")
        raise RuntimeError(f"Failed to retrieve file from MinIO: {e}") from e


def process_pdf_pages(file_data: bytes, filename: str) -> list[dict[str, Any]]:
    logger.info("Processing PDF file: %s", filename)
    images = convert_from_bytes(file_data)
    ocr_pages_results = []
    for i, image in enumerate(images):
        page_number = i + 1
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format="PNG")
        img_bytes = img_byte_arr.getvalue()

        page_filename = f"page_{page_number}_{filename}.png"
        ocr_text = call_ai_service(img_bytes, page_filename)
        ocr_pages_results.append(
            {"page_number": page_number, "text": ocr_text},
        )
    return ocr_pages_results


def process_single_image(
    file_data: bytes,
    filename: str,
) -> list[dict[str, Any]]:
    logger.info("Processing image file: %s", filename)
    ocr_text = call_ai_service(file_data, filename)
    return [{"page_number": 1, "text": ocr_text}]


def process_document(file: File, file_data: bytes) -> list[dict[str, Any]]:
    if "pdf" in file.file_type:
        return process_pdf_pages(file_data, file.filename)
    return process_single_image(file_data, file.filename)


def store_ocr_results(
    db: Session,
    task: Task,
    file: File,
    ocr_pages_results: list[dict[str, Any]],
) -> None:
    minio_client = get_minio_client()
    result_storage = ResultStorage(minio_client)

    for page_data in ocr_pages_results:
        page_number = page_data["page_number"]
        page_text = page_data["text"]
        result_path = f"{file.id}/page_{page_number}.json"
        result_content = json.dumps({"text": page_text})

        result_storage.upload_result(
            result_content,
            result_path,
            BUCKET_RESULT_STORAGE,
        )

        page_result_entry = PageResult(
            task_id=task.id,
            file_id=file.id,
            page_number=page_number,
            result_path=result_path,
        )
        page_result_repo.add(db, page_result_entry)


def update_task_to_completed(
    db: Session,
    task: Task,
    file: File,
    total_pages: int,
) -> None:
    file.total_pages = total_pages
    task.status = TaskStatus.COMPLETED
    db.commit()


def handle_processing_error(
    task_id: uuid.UUID,
    db: Session,
    error: Exception,
) -> None:
    logger.exception("Processing failed for task %s", task_id)
    db.rollback()
    update_task_status_in_new_session(task_id, TaskStatus.FAILED, str(error))


@celery_app.task
def process_file(task_id_str: str) -> None:
    task_id = uuid.UUID(task_id_str)
    db = SessionLocal()
    try:
        task, file = get_validated_task_and_file(db, task_id)

        task.status = TaskStatus.PROCESSING
        db.commit()

        file_data = download_file_from_minio(file.storage_path)

        ocr_pages_results = process_document(file, file_data)

        store_ocr_results(db, task, file, ocr_pages_results)

        total_pages = len(ocr_pages_results)
        update_task_to_completed(db, task, file, total_pages)

    except (
        ValueError,
        RuntimeError,
        requests.exceptions.RequestException,
        TypeError,
        KeyError,
    ) as e:
        handle_processing_error(task_id, db, e)
    finally:
        db.close()


def call_ai_service(image_bytes: bytes, filename: str) -> str:
    logger.info("Sending request to AI service for file: %s", filename)
    files = {"file": (filename, image_bytes, "image/png")}
    try:
        response = requests.post(AI_SERVICE_URL, files=files, timeout=300)
        response.raise_for_status()
        result = response.json()
        logger.info("Received response from AI service for file: %s", filename)
        return result.get("data", {}).get("text", "")
    except requests.exceptions.RequestException as e:
        logger.exception("Failed to call AI service for file %s", filename)
        raise RuntimeError(f"AI service request failed: {e}") from e


def update_task_status_in_new_session(
    task_id: uuid.UUID,
    status: TaskStatus,
    error_message: str | None = None,
) -> None:
    session = SessionLocal()
    try:
        task = task_repo.get_by_id(session, task_id)
        if task:
            task.status = status
            task.error_message = error_message
            session.commit()
    except Exception:
        logger.exception(
            "Failed to update task %s status to %s",
            task_id,
            status,
        )
        session.rollback()
    finally:
        session.close()
