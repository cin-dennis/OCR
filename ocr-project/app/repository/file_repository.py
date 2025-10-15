from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.file import File


class FileRepository:
    def __init__(self, session: Session) -> None:
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
