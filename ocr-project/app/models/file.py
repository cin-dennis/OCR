import uuid
from sqlalchemy import Column, String, DateTime, func, Integer
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False, unique=True)
    file_type = Column(String, nullable=False)
    total_pages = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, server_default=func.now(), nullable=False)