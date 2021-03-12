from typing import Optional
from pydantic import BaseModel, ValidationError, validator, Field
from email_validator import EmailNotValidError, validate_email
from datetime import datetime

class UserBase(BaseModel):
    username: str = Field(title='Username')
    email: str = Field(title='Email')
    password: str = Field(title='Password')
    disabled: Optional[bool] = None

class UserCreate(UserBase):
    confirm_password: str = Field(title='Confirm Password')

    @validator('username')
    def username_valid(cls, v):
        if len(v) < 2 or len(v) > 20:
            raise ValueError('Username must be between 2 and 20 characters')
        return v

    @validator('email')
    def email_valid(cls, v):
        try:
            validate_email(v)
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

class TokenData(BaseModel):
    username: Optional[str] = None