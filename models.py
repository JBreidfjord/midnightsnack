from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, DateTime, Text, PickleType, Table
from sqlalchemy.orm import backref, relationship
from datetime import datetime
from slugify import slugify

from database import Base

def slug_default(context):
    return slugify(context.get_current_parameters()['title'], max_length=20)

tag_assoc_table = Table('association', Base.metadata,
    Column('post_id', Integer, ForeignKey('posts.id')),
    Column('tag_id', Integer, ForeignKey('tags.id'))
)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(20), unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    image_file = Column(String, nullable=False, default='default.jpg')
    password = Column(String(60), nullable=False)
    scopes = Column(PickleType, default=[])
    disabled = Column(Boolean, default=False)

    posts = relationship('Post', backref='author', lazy=True)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

class Post(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    slug = Column(String(20), nullable=False, default=slug_default, onupdate=slug_default)
    date_posted = Column(DateTime, nullable=False, default=datetime.today().strftime('%Y-%m-%d'))
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    description = Column(String)
    image_text = Column(String)
    photographer_name = Column(String)
    photographer_url = Column(String)
    keywords = Column(String)

    tags = relationship('Tag', secondary=tag_assoc_table, back_populates='posts')

    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')"

class Tag(Base):
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    posts = relationship('Post', secondary=tag_assoc_table, back_populates='tags')