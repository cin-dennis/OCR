from celery import Celery

from app.core.config import settings

broker_url = (
    f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}"
    f"@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}//"
)
result_backend_url = (
    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
)

celery_app = Celery(
    "ocr_project",
    broker=broker_url,
    backend=result_backend_url,
    include=[
        "app.worker.file_process_worker",
    ],
)
