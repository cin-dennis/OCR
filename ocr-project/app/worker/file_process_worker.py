import json
import logging
import uuid
from io import BytesIO
from typing import Any

import requests
from celery import chord, group
from celery.exceptions import CeleryError
from minio.error import S3Error
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError
from PIL import Image
from sqlalchemy.exc import SQLAlchemyError
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


@celery_app.task
def process_file(task_id_str: str) -> None:
    task_id = uuid.UUID(task_id_str)
    db = SessionLocal()
    try:
        task = task_repo.get_by_id(db, task_id)
        if not task:
            logger.warning("Task %s not found.", task_id)
            return

        file = file_repo.get_by_id(db, task.file_id)
        if not file:
            logger.warning("File for task %s not found.", task_id)
            task.status = TaskStatus.FAILED
            task.error_message = "File metadata not found in database."
            db.commit()
            return

        task.status = TaskStatus.PROCESSING
        db.commit()

        file_data = download_file_from_minio(file.storage_path)

        callback = finalize_ocr_processing.s(task_id_str=task_id_str)

        if "pdf" in file.file_type:
            images = convert_from_bytes(file_data)
            header = group(
                process_single_page_ocr.s(
                    image_bytes=img_to_bytes(image),
                    filename=f"page_{i + 1}_{file.filename}.png",
                    page_number=i + 1,
                )
                for i, image in enumerate(images)
            )
        else:
            header = group(
                process_single_page_ocr.s(
                    image_bytes=file_data,
                    filename=file.filename,
                    page_number=1,
                ),
            )

        job = chord(header, callback)
        job.apply_async()

    except SQLAlchemyError:
        logger.exception(
            "Database error during task setup for task %s. Rolling back.",
            task_id,
        )
        db.rollback()

    except S3Error as e:
        logger.exception(
            "Failed to download file from MinIO for task %s.",
            task_id,
        )
        handle_processing_error(task_id, db, f"Storage access error: {e}")

    except (PDFPageCountError, PDFSyntaxError) as e:
        logger.exception(
            "Failed to process PDF file for task %s.",
            task_id,
        )
        handle_processing_error(task_id, db, f"PDF processing error: {e}")

    except CeleryError as e:
        logger.exception(
            "Failed to queue child tasks (chord) for task %s.",
            task_id,
        )
        handle_processing_error(task_id, db, f"Task queuing error: {e}")

    except Exception as e:
        logger.exception(
            "An unexpected error occurred"
            " while starting processing for task %s.",
            task_id,
        )
        handle_processing_error(
            task_id,
            db,
            f"An unexpected error occurred: {e}",
        )

    finally:
        db.close()


@celery_app.task
def process_single_page_ocr(
    image_bytes: bytes,
    filename: str,
    page_number: int,
) -> dict:
    logger.info("Processing page %d for file: %s", page_number, filename)
    ocr_text = call_ai_service(image_bytes, filename)
    return {"page_number": page_number, "text": ocr_text}


@celery_app.task
def finalize_ocr_processing(
    ocr_pages_results: list[dict],
    task_id_str: str,
) -> None:
    task_id = uuid.UUID(task_id_str)
    db = SessionLocal()
    try:
        logger.info("Finalizing processing for task %s.", task_id)
        task = task_repo.get_by_id(db, task_id)
        if not task:
            logger.error("Task %s not found for finalization.", task_id)
            return

        file = file_repo.get_by_id(db, task.file_id)
        if not file:
            logger.error(
                "File for task %s not found for finalization.",
                task_id,
            )
            return

        sorted_results = sorted(
            ocr_pages_results,
            key=lambda r: r["page_number"],
        )

        store_ocr_results(db, task, file, sorted_results)
        update_task_to_completed(db, task, file, len(sorted_results))
        logger.info("Successfully completed task %s.", task_id)
    except Exception as e:
        logger.exception("Error during finalization for task %s", task_id)
        handle_processing_error(task_id, db, str(e))
    finally:
        db.close()


def download_file_from_minio(file_storage_path: str) -> bytes:
    minio_client = get_minio_client()
    try:
        file_object = minio_client.get_object(
            BUCKET_FILE_STORAGE,
            file_storage_path,
        )
        return file_object.read()
    except S3Error:
        logger.exception("Failed to retrieve file from MinIO")
        raise


def call_ai_service(image_bytes: bytes, filename: str) -> str:
    logger.info(
        "Sending multipart/form-data request to AI service for file: %s",
        filename,
    )
    form_data = {"job_id": str(uuid.uuid4())}
    file_data = {"input": (filename, image_bytes, "image/png")}

    try:
        response = requests.post(
            AI_SERVICE_URL,
            data=form_data,
            files=file_data,
            timeout=300,
        )

        result = response.json()

        logger.info("Full AI service response for %s: %s", filename, result)

        error_code = result.get("error_code")
        error_message = result.get("error_message")
        if error_code or error_message:
            error_details = (
                f"AI service returned an application error:"
                f" Code='{error_code}', Message='{error_message}'"
            )
            logger.error(error_details)
            raise RuntimeError(error_details)

        ocr_results_list = result.get("result", [])

        if not ocr_results_list:
            logger.warning(
                "AI service returned empty result for file: %s",
                filename,
            )
            return ""

        # Lấy phần tử đầu tiên
        first_result = ocr_results_list[0]

        if not isinstance(first_result, dict):
            logger.warning(
                "Unexpected result format for file %s: expected dict, got %s",
                filename,
                type(first_result).__name__,
            )
            return ""

        layout = first_result.get("layout", [])

        if not layout:
            logger.warning(
                "No layout data found in result for file: %s",
                filename,
            )
            return ""

        texts = []
        for item in layout:
            if item.get("type") == "textline":
                text = item.get("text", "")
                if text:
                    texts.append(text)

        ocr_text = "\n".join(texts)

        logger.info(
            "Successfully extracted OCR text for file: %s (length: %d chars)",
            filename,
            len(ocr_text),
        )

    except requests.exceptions.RequestException:
        logger.exception("Failed to call AI service for file %s", filename)
        raise
    except json.JSONDecodeError:
        logger.exception(
            "Failed to decode JSON response from AI service for file %s",
            filename,
        )
        raise

    return ocr_text


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
        page_text = page_data.get("text", "")
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
    error: str,
) -> None:
    logger.exception("Processing failed for task %s", task_id)
    db.rollback()
    session_for_update = SessionLocal()
    try:
        task = task_repo.get_by_id(session_for_update, task_id)
        if task and task.status != TaskStatus.FAILED:
            task.status = TaskStatus.FAILED
            task.error_message = str(error)
            session_for_update.commit()
    except SQLAlchemyError:
        logger.exception(
            "Failed to update task %s status to FAILED.",
            task_id,
        )
        session_for_update.rollback()
    except Exception:
        logger.exception(
            "Unexpected error while updating task %s status to FAILED.",
            task_id,
        )
    finally:
        session_for_update.close()


def img_to_bytes(image: Image.Image) -> bytes:
    img_byte_arr = BytesIO()
    image.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue()
