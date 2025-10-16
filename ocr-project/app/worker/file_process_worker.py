# ocr-project/app/worker/file_process_worker.py

import json
import logging
import uuid

from minio.error import S3Error

from app.constant.constant import BUCKET_FILE_STORAGE, BUCKET_RESULT_STORAGE
from app.db.session import SessionLocal
from app.models import PageResult
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
            logger.error("Task with ID %s not found.", task_id)
            return

        file = file_repo.get_by_id(db, task.file_id)
        if not file:
            logger.error(
                "File with ID %s not found for task %s.",
                task.file_id,
                task_id,
            )
            update_task_status_in_new_session(
                task_id,
                TaskStatus.FAILED,
                "Associated file not found.",
            )
            return

        task.status = TaskStatus.PROCESSING
        db.commit()

        minio_client = get_minio_client()
        result_storage = ResultStorage(minio_client)

        try:
            file_object = minio_client.get_object(
                BUCKET_FILE_STORAGE,
                file.storage_path,
            )
            file_data = file_object.read()
        except S3Error as e:
            raise RuntimeError(
                f"Failed to retrieve file from MinIO: {e}",
            ) from e

        ocr_result = mock_ai_service(file_data, file.file_type)

        for page_data in ocr_result.get("pages", []):
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

        file.total_pages = ocr_result.get("total_pages", 0)
        task.status = TaskStatus.COMPLETED

        db.commit()
    except Exception as e:
        logger.exception("Processing failed for task %s", task_id)
        db.rollback()
        update_task_status_in_new_session(task_id, TaskStatus.FAILED, str(e))
    finally:
        db.close()


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


def mock_ai_service(file_data: bytes, file_type: str) -> dict:
    logger.info("Mock AI service processing file of type %s", file_type)
    logger.debug("File data size: %d bytes", len(file_data))
    if "pdf" in file_type:
        return {
            "total_pages": 3,
            "pages": [
                {"page_number": 1, "text": "This is the content of page 1."},
                {"page_number": 2, "text": "This is the content of page 2."},
                {"page_number": 3, "text": "This is the content of page 3."},
            ],
        }
    return {
        "total_pages": 1,
        "pages": [
            {"page_number": 1, "text": "This is the content of the image."},
        ],
    }
