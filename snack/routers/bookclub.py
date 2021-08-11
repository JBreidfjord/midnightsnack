from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, Security
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from snack import auth
from snack.bookclub import crud, schema
from snack.bookclub.models import Book
from snack.bookclub.scraper import get_book_data
from snack.dependencies import get_book_obj, get_db, get_poll_obj
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/bookclub", dependencies=[Security(auth.verify_token, scopes=["bookclub"])]
)

templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    polls = crud.get_all_polls(db)
    polls = [
        {
            "date": datetime.strptime(str(poll.date), "%Y%m").strftime("%B %Y"),
            "id": poll.id,
            "primary": poll.primary,
        }
        for poll in polls
        if not poll.finished
    ]

    books = crud.get_all_books(db)
    books = [
        {"id": book.id, "title": book.title, "author": book.author}
        for book in books
        if not book.read and not book.veto and not book.current
    ]

    current = crud.get_current_book(db)

    response = templates.TemplateResponse(
        "bookclub.html", {"request": request, "polls": polls, "books": books, "current": current}
    )
    response.delete_cookie(key="BookSuccess")
    response.delete_cookie(key="BookErrors")
    return response


# Books
@router.post("/books/new", response_class=RedirectResponse)
async def create_book(request: Request, url: str = Form(...), db: Session = Depends(get_db)):
    response = RedirectResponse(url="/bookclub", status_code=303)

    # Validate URL, returning error cookie if invalid
    try:
        schema.BookURL(url=url)
    except ValidationError as exception:
        errors = [error["msg"] for error in exception.errors()]
        error_str = ":".join(errors)
        response.set_cookie(key="BookErrors", value=error_str, max_age=30, expires=30)
        return response

    book_data = await get_book_data(db, url)
    book = Book(**book_data)

    # Return error if book exists in database
    if crud.get_book(db, title=book.title) is not None:
        response.set_cookie(key="BookErrors", value="Book already exists", max_age=30, expires=30)
        return response

    db.add(book)
    db.commit()

    response.set_cookie(key="BookSuccess", value=book.title, max_age=30, expires=30)
    return response


@router.get("/books/{id}", response_class=HTMLResponse)
async def get_book(request: Request, id: int, db: Session = Depends(get_db)):
    book = get_book_obj(db, id)
    return templates.TemplateResponse("bookpage.html", {"request": request, "book": book})


# Polls
@router.post(
    "/polls/new",
    response_class=RedirectResponse,
    dependencies=[Security(auth.verify_token, scopes=["admin"])],
)
async def create_poll(request: Request, date: str = Form(...), db: Session = Depends(get_db)):
    date = int(date.replace("-", ""))
    if crud.check_poll_exists(db, date):
        return RedirectResponse("/admin", status_code=303)
    poll = {"date": date, "primary": True}
    crud.create_poll(db, poll)
    return RedirectResponse("/admin", status_code=303)


@router.post(
    "/polls/complete",
    response_class=RedirectResponse,
    dependencies=[Security(auth.verify_token, scopes=["admin"])],
)
async def complete_poll(request: Request, id: int = Form(...), db: Session = Depends(get_db)):
    crud.complete_poll(db, id)
    return RedirectResponse("/admin", status_code=303)


@router.get("/polls/{id}", response_class=HTMLResponse)
async def get_poll(request: Request, id: int, db: Session = Depends(get_db)):
    # Verify user hasn't already voted in this poll
    if request.cookies.get("User") in crud.get_voters(db, id):
        return RedirectResponse("/bookclub", status_code=303)

    poll = get_poll_obj(db, id)
    poll = {
        "date": datetime.strptime(str(poll.date), "%Y%m").strftime("%B %Y"),
        "id": poll.id,
        "primary": poll.primary,
        "choices": poll.choices,
    }

    html = "bookpoll_primary.html" if poll["primary"] else "bookpoll_secondary.html"
    return templates.TemplateResponse(html, {"request": request, "poll": poll})


@router.post("/polls/{id}", response_class=RedirectResponse)
async def submit_poll(
    request: Request, id: int, user: str = Form(...), db: Session = Depends(get_db)
):
    formdata = await request.form()

    choice_values = []
    for k, v in formdata.items():
        if k.isdigit():
            choice_id = int(k)
            votes = 1 if v == "on" else int(v)
            choice_values.append((choice_id, votes))

    # Invert values for secondary polls
    if len(choice_values) > 0:
        if max(choice_values, key=lambda x: x[1])[1] > 1:
            choice_values = list(
                map(lambda x: (x[0], len(choice_values) + 1 - x[1]), choice_values)
            )

    for choice_id, votes in choice_values:
        crud.update_vote(db, choice_id, votes)
    crud.update_voters(db, id, user)

    return RedirectResponse(url="/bookclub", status_code=303)
