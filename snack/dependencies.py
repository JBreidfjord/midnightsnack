from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from snack import crud
from snack.bookclub.crud import get_book, get_poll
from snack.database import SessionLocal


def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_post_obj(db: Session, slug: str):
    obj = crud.get_post(db, slug)
    if obj is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return obj


def get_poll_obj(db: Session, poll_id: int):
    obj = get_poll(db, poll_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Poll not found")
    return obj


def get_book_obj(db: Session, book_id: int):
    obj = get_book(db, book_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return obj
