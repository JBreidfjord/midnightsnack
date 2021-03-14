from sqlalchemy import select
from database import SessionLocal
import models
from typing import Optional
from pydantic import BaseModel, ValidationError, validator, Field
from email_validator import EmailNotValidError, validate_email
from datetime import datetime

db = SessionLocal()

class UserBase(BaseModel):
    username: str = Field(title='Username')
    email: str = Field(title='Email')
    disabled: Optional[bool] = None

class UserInfo(UserBase):
    password: str = Field(title='Password')

    class Config:
        orm_mode = True

class UserCreate(UserInfo):
    confirm_password: str = Field(title='Confirm Password')

    @validator('username')
    def username_valid(cls, v):
        if len(v) < 2 or len(v) > 20:
            raise ValueError('Username must be between 2 and 20 characters')
        if db.execute(select(models.User.username).where(models.User.username == v)).scalar():
            raise ValueError('Username already exists')
        return v

    @validator('email')
    def email_valid(cls, v):
        try:
            validate_email(v)
            if db.execute(select(models.User.email).where(models.User.email == v)).scalar():
                raise ValueError('Email already exists')
            return v
        except EmailNotValidError:
            raise ValueError('Email is not valid')

    @validator('password')
    def password_valid(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

    @validator('confirm_password')
    def confirm_password_valid(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')

class User(UserBase):
    pass

    class Config:
        orm_mode = True

class PostBase(BaseModel):
    title: str
    date_posted: Optional[datetime] = datetime.utcnow()
    content: str
    user_id: int

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