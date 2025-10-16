import uuid

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False, unique=True)
    file_type = Column(String, nullable=False)
    total_pages = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, server_default=func.now(), nullable=False)

    task = relationship(
        "Task",
        back_populates="file",
        uselist=False,
        cascade="all, delete-orphan",
    )
    page_results = relationship(
        "PageResult",
        back_populates="file",
        cascade="all, delete-orphan",
    )
