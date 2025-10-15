from app.repository.file_repository import file_repo

from .celery import celery_app


@celery_app.task
def process_file(file_id: str) -> None:
    file = file_repo.get_by_id(file_id)
    if not file:
        raise ValueError(f"File with ID {file_id} not found")
    # TODO: Create Task Record in the database

    # TODO: Update file status in the database: (PROCESSING)

    # TODO: Call to AI Service to process the file

    # TODO: Update file status in the database:
    #  (Number Page, Task Status: COMPLETED/FAILED)

    # TODO: Create Page Results in the database
