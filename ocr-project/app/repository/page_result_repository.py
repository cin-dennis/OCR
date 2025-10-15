from sqlalchemy.exc import SQLAlchemyError

from app.db.session import session
from app.models import PageResult


class PageResultRepository:
    def __init__(self) -> None:
        self.session = session

    def add(self, page_result: PageResult) -> None:
        try:
            self.session.add(page_result)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            self.session.close()
