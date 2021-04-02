from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
import crud

def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

def get_post_obj(db: Session, slug: str):
    obj = crud.get_post(db=db, slug=slug)
    if obj is None:
        raise HTTPException(status_code=404, detail='Post not found')
    return obj
