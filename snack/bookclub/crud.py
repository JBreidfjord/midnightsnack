from snack.bookclub import schema
from snack.bookclub.models import Book, Choice, Poll
from sqlalchemy.orm import Session


# Polls
def create_poll(db: Session, poll: schema.PollCreate):
    """Adds a new poll to the database. Returns the created poll object."""
    obj = Poll(**poll.dict())
    db.add(obj)
    db.commit()
    return obj


def get_poll(db: Session, poll_id: int):
    return db.query(Poll).filter(Poll.id == poll_id).first()


def get_all_polls(db: Session):
    return db.query(Poll).all()


def get_poll_info(db: Session, poll_id: int):
    stmt = db.query(Choice).filter(Choice.poll_id == poll_id).join(Choice.book_id)
    obj = db.execute(stmt)
    return obj


def edit_poll(db: Session, poll: schema.Poll):
    obj = db.query(Poll).filter(Poll.id == poll.id).first()
    obj.date = poll.date
    db.commit()
    return obj


def delete_poll(db: Session, poll_id: int):
    db.query(Poll).filter(Poll.id == poll_id).delete()
    db.commit()


# Choices
def create_choice(db: Session, poll_id: int, choice: schema.ChoiceCreate):
    obj = Choice(**choice.dict(), poll_id=poll_id)
    db.add(obj)
    db.commit()
    return obj


def update_vote(db: Session, choice_id: int, votes: int = 1):
    obj = db.query(Choice).filter(Choice.id == choice_id).first()
    obj.votes += votes
    db.commit()
    return obj


# Books
def create_book(db: Session, book: schema.BookCreate):
    obj = Book(**book.dict())
    db.add(obj)
    db.commit()
    return obj


def get_book(db: Session, book_id: int):
    return db.query(Book).filter(Book.id == book_id).first()


def get_all_books(db: Session):
    return db.query(Book).all()


def delete_book(db: Session, book_id: int):
    db.query(Book).filter(Book.id == book_id).delete()
    db.commit()
