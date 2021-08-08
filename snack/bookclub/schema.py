from pydantic import BaseModel


class BookBase(BaseModel):
    title: str
    author: str
    page_count: int
    description: str
    image: str


class BookCreate(BookBase):
    pass


class BookGenerate(BookBase):
    pass


class Book(BookBase):
    id: int
    read: bool = False
    veto: bool = False

    class Config:
        orm_mode = True


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


class PollCreate(PollBase):
    pass


class Poll(PollBase):
    id: int

    class Config:
        orm_mode = True


class PollInfo(Poll):
    choices: list[ChoiceList] = []
