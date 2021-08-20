from snack.bookclub import schema
from snack.bookclub.models import Book, Choice, Poll
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session


# Polls
def create_poll(db: Session, poll: schema.PollCreate):
    """Adds a new poll to the database. Returns the created poll object."""
    obj = Poll(**poll)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    _update_choices(db, obj)
    db.refresh(obj)
    return obj


def _update_choices(db: Session, poll: schema.Poll):
    """Adds existing choices to poll."""
    if poll.primary:
        for book in get_all_books(db):
            if not book.read and not book.veto and not book.current:
                create_choice(db, poll.id, {"book_id": book.id})
    else:
        primary_id = (
            db.query(Poll.id).filter(Poll.date == poll.date).filter(Poll.primary == True).scalar()
        )
        max_votes = db.execute(
            select(func.max(Choice.votes)).where(Choice.poll_id == primary_id)
        ).scalar()
        results = (
            db.query(Book)
            .filter(Choice.book_id == Book.id)
            .filter(Choice.poll_id == primary_id)
            .filter(Choice.votes == max_votes)
            .all()
        )
        for book in results:
            if not book.read and not book.veto and not book.current:
                create_choice(db, poll.id, {"book_id": book.id})


def complete_poll(db: Session, poll_id: int):
    """Finalizes the given poll and either creates the secondary poll
    or updates the current book to be read."""
    obj = db.query(Poll).filter(Poll.id == poll_id).first()
    obj.finished = True
    db.commit()
    if obj.primary:
        _check_veto(db, poll_id)
        create_poll(db, {"date": obj.date, "primary": False})
    else:
        _update_current(db, poll_id)


def _update_current(db: Session, poll_id: int):
    """Update current book with results from poll."""
    # Set current book as read
    current = get_current_book(db)
    if current is not None:
        current.current = False
        current.read = True
        db.commit()

    # Calculate result
    max_votes = db.execute(select(func.max(Choice.votes)).where(Choice.poll_id == poll_id)).scalar()
    result = (
        db.query(Book)
        .filter(Choice.book_id == Book.id)
        .filter(Choice.poll_id == poll_id)
        .filter(Choice.votes == max_votes)
        .one()
    )
    # Set new current book
    result.current = True
    db.commit()


def _check_veto(db: Session, poll_id: int):
    """Sets veto on books with 1 or less votes in primary poll."""
    objs = (
        db.query(Book)
        .filter(Choice.book_id == Book.id)
        .filter(Choice.poll_id == poll_id)
        .filter(Choice.votes <= 1)
        .all()
    )
    for obj in objs:
        obj.veto = True
        db.commit()


def get_poll(db: Session, poll_id: int):
    return db.query(Poll).filter(Poll.id == poll_id).first()


def get_all_polls(db: Session):
    return db.query(Poll).all()


def get_poll_info(db: Session, poll_id: int):
    stmt = db.query(Choice).filter(Choice.poll_id == poll_id).join(Choice.book_id)
    obj = db.execute(stmt)
    return obj


def check_poll_exists(db: Session, date: int):
    obj = db.query(Poll).filter(Poll.date == date).filter(Poll.primary == True).scalar()
    return obj is not None


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
    obj = Choice(**choice, poll_id=poll_id)
    db.add(obj)
    db.commit()
    return obj


def update_vote(db: Session, choice_id: int, votes: int = 1):
    obj = db.query(Choice).filter(Choice.id == choice_id).first()
    obj.votes += votes
    db.commit()
    return obj


def update_voters(db: Session, poll_id: int, user: str):
    obj = db.query(Poll).filter(Poll.id == poll_id).first()
    obj.users_voted.append(user)
    db.execute(update(Poll).where(Poll.id == poll_id).values(users_voted=obj.users_voted))
    db.commit()
    return obj


def get_voters(db: Session, poll_id: int) -> list[str]:
    obj = db.query(Poll).filter(Poll.id == poll_id).first()
    return obj.users_voted


# Books
def create_book(db: Session, book: schema.BookCreate):
    obj = Book(**book.dict())
    db.add(obj)
    db.commit()
    return obj


def get_book(db: Session, book_id: int = None, title: str = None):
    """Get a book object from the database by ID or title.
    ID will take priority if both are given."""
    if book_id is not None:
        return db.query(Book).filter(Book.id == book_id).first()
    elif title is not None:
        return db.query(Book).filter(Book.title == title).first()
    raise ValueError("ID or title must be given")


def get_all_books(db: Session):
    return db.query(Book).all()


def get_current_book(db: Session):
    return db.query(Book).filter(Book.current == True).one_or_none()


def delete_book(db: Session, book_id: int):
    db.query(Book).filter(Book.id == book_id).delete()
    db.commit()
