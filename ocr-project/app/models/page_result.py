import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class PageResult(Base):
    __tablename__ = "page_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id"),
        nullable=False,
    )
    file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("files.id"),
        nullable=False,
    )
    page_number = Column(Integer, nullable=False)
    result_path = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    task = relationship("Task", backref="page_results", uselist=False)
    file = relationship("File", backref="page_results", uselist=False)
