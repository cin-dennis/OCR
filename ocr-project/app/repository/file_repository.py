from sqlalchemy.orm import Session

from app.models.file import File


class FileRepository:
    def add(self, db: Session, file: File) -> File:
        db.add(file)
        db.flush()
        return file

    def get_by_id(self, db: Session, file_id: str) -> File | None:
        return db.query(File).filter(File.id == file_id).first()

    def save(self, db: Session, file: File) -> File:
        db.add(file)
        db.flush()
        return file


file_repo = FileRepository()
