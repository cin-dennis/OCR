from datetime import datetime

from pydantic import BaseModel


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
