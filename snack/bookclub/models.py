from snack.database import Base
from sqlalchemy import ARRAY, Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship


class Poll(Base):
    __tablename__ = "polls"
    id = Column(Integer, primary_key=True)
    date = Column(Integer)  # YYYYMM
    primary = Column(Boolean)
    users_voted = Column(ARRAY(String), default=[])
    finished = Column(Boolean, default=False)

    choices = relationship("Choice", back_populates="poll")


class Choice(Base):
    __tablename__ = "choices"
    id = Column(Integer, primary_key=True)
    poll_id = Column(Integer, ForeignKey("polls.id", ondelete="CASCADE"))
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"))
    votes = Column(Integer, default=0)

    book = relationship("Book")
    poll = relationship("Poll", back_populates="choices")


class Book(Base):
    __tablename__ = "books"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    author = Column(String)
    page_count = Column(Integer)
    description = Column(String)
    image = Column(String)
    current = Column(Boolean, default=False)
    read = Column(Boolean, default=False)
    veto = Column(Boolean, default=False)
