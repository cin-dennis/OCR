from sqlalchemy.exc import SQLAlchemyError

from app.db.session import session
from app.models.file import File


class FileRepository:
    def __init__(self) -> None:
        self.session = session

    def save(self, file: File) -> None:
        try:
            self.session.add(file)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            self.session.close()

    def get_by_id(self, file_id: str) -> File | None:
        try:
            return self.session.query(File).filter(File.id == file_id).first()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            self.session.close()


file_repo = FileRepository()
