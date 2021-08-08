from datetime import datetime
from typing import List, Optional

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, Field, HttpUrl, validator
from slugify import slugify
from sqlalchemy import select

from snack import models
from snack.database import SessionLocal

db = SessionLocal()


class UserBase(BaseModel):
    username: str = Field(title="Username")
    email: str = Field(title="Email")
    disabled: Optional[bool] = None


class UserInfo(UserBase):
    password: str = Field(title="Password")
    scopes: Optional[list] = []

    class Config:
        orm_mode = True


class UserCreate(UserInfo):
    confirm_password: str = Field(title="Confirm Password")

    @validator("username")
    def username_valid(cls, v):
        if len(v) < 2 or len(v) > 20:
            raise ValueError("Username must be between 2 and 20 characters")
        if db.execute(select(models.User.username).where(models.User.username == v)).scalar():
            raise ValueError("Username already exists")
        return v

    @validator("email")
    def email_valid(cls, v):
        try:
            validate_email(v)
            if db.execute(select(models.User.email).where(models.User.email == v)).scalar():
                raise ValueError("Email already exists")
            return v
        except EmailNotValidError:
            raise ValueError("Email is not valid")

    @validator("password")
    def password_valid(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @validator("confirm_password")
    def confirm_password_valid(cls, v, values):
        if "password" in values and v != values["password"]:
            raise ValueError("Passwords do not match")


class User(UserBase):
    pass

    class Config:
        orm_mode = True


class PostBase(BaseModel):
    title: str
    date_posted: Optional[datetime] = datetime.today().strftime("%Y-%m-%d")
    content: str
    user_id: int
    slug: str
    description: str
    image_text: str
    photographer_name: str
    photographer_url: HttpUrl
    keywords: str
    tags: List[str]


class PostCreate(PostBase):
    pass


class PostInfo(PostBase):
    pass

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

    class Config:
        arbitrary_types_allowed = True


class TokenData(BaseModel):
    username: Optional[str] = None
    scopes: List[str] = []
