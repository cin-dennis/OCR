from app.models import Task
from app.repository.file_repository import file_repo
from app.repository.task_repository import task_repo

from .celery import celery_app


@celery_app.task
def process_file(file_id: str) -> None:
    file = file_repo.get_by_id(file_id)
    if not file:
        raise ValueError(f"File with ID {file_id} not found")
    task = Task(
        file_id=file_id,
    )
    task_repo.add(task)

    # TODO: Call to AI Service to process the file

    # TODO: Update file status in the database:

    # TODO: Create Page Results in the database
