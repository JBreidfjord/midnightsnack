from sqlalchemy import select, delete, update, insert
from sqlalchemy.orm import Session
from models import User, Post
import schema


# Post
def create_post(db: Session, post: schema.PostCreate):
    '''Creates an instance of the User class, taking the database session and post info defined by the schema as inputs'''
    obj = Post(**post)
    db.add(obj)
    db.commit()
    return obj

def get_all_posts(db: Session):
    return db.execute(select(Post)).scalars()

def get_post(db: Session, slug: str):
    return db.execute(select(Post).where(Post.slug == slug)).scalar()

def del_post(db: Session, slug: str):
    db.execute(delete(Post).where(Post.slug == slug))
    db.commit()


# User
def get_user(db: Session, username: str):
    pass