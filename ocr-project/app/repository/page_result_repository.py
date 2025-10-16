from sqlalchemy.orm import Session

from app.models import PageResult


class PageResultRepository:
    def add(self, db: Session, page_result: PageResult) -> PageResult:
        db.add(page_result)
        db.flush()
        return page_result


page_result_repo = PageResultRepository()
