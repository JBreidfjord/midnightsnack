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
    return db.query(Post).all()

def get_post(db: Session, post_id: int):
    return db.query(Post).filter(Post.id == post_id).scalar()