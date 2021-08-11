from pydantic import BaseModel, HttpUrl, validator


class BookBase(BaseModel):
    title: str
    author: str
    page_count: int
    description: str
    image: str


class BookCreate(BookBase):
    pass


class Book(BookBase):
    id: int
    current: bool = False
    read: bool = False
    veto: bool = False

    class Config:
        orm_mode = True


class BookURL(BaseModel):
    url: HttpUrl

    @validator("url")
    def check_host(cls, v):
        if v.host != "www.goodreads.com":
            raise ValueError("Must be a Goodreads URL")
        if not v.path.startswith("/book/show"):
            raise ValueError("Must be a book's info page")


class ChoiceBase(BaseModel):
    votes: int = 0


class ChoiceCreate(ChoiceBase):
    book_id: int


class ChoiceList(ChoiceBase):
    id: int
    book: Book

    class Config:
        orm_mode = True


class PollBase(BaseModel):
    date: int
    primary: bool
    finished: bool = False


class PollCreate(PollBase):
    pass


class Poll(PollBase):
    id: int

    class Config:
        orm_mode = True


class PollInfo(Poll):
    choices: list[ChoiceList] = []
