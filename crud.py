from sqlalchemy import select, delete, update, insert
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import User, Post, Tag
from typing import List
from pathlib import Path
import schema


# Post
def create_post(db: Session, post: schema.PostCreate):
    '''Creates an instance of the User class, taking the database session and post info defined by the schema as inputs'''
    print(post)
    obj = Post(**post)
    db.add(obj)
    db.commit()
    return obj

def get_all_posts(db: Session):
    return db.execute(select(Post)).scalars()

def get_post(db: Session, slug: str):
    obj = db.execute(select(Post).where(Post.slug == slug)).scalar()
    if not obj:
        return None
    for file in Path(f'./static/posts/{slug}/').iterdir():
        if 'headerImage' in file.name:
            img = file
        if '.html' in file.name:
            article = file
    return {'post_obj': obj, 'img_path': img, 'article_path': article}

def del_post(db: Session, slug: str):
    db.execute(delete(Post).where(Post.slug == slug))
    db.commit()

# Tags
def create_tag(db: Session, tags: List[str]):
    tag_objs = []
    for tag in tags:
        try:
            obj = Tag(name=tag)
            db.add(obj)
            db.commit()
            obj.append(tag_objs)
        except IntegrityError:
            pass
    return tag_objs

# User
def get_user(db: Session, username: str):
    pass