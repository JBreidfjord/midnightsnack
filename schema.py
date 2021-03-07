from typing import Optional
from pydantic import BaseModel, EmailStr, ValidationError, validator, Field
from datetime import datetime

class UserBase(BaseModel):
    username: str = Field(title='Username')
    email: EmailStr = Field(title='Email')
    password: str = Field(title='Password')
    confirm_password: str = Field(title='Confirm Password')

class UserCreate(UserBase):
    @validator('username')
    def username_valid(cls, v):
        if len(v) < 2 or len(v) > 20:
            raise ValueError('Username must be between 2 and 20 characters')
        return v

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

# # Testing
# user = UserBase(
#     username = 'jbreidfjord',
#     email = 'jbreidfjord@gmail.com',
#     password = 'testyboi',
#     confirm_password = 'testyboi'
# )

# try:
#     UserBase(
#         username = 'jbreidfjord',
#         email = 'jbreidfjord@gmail.com',
#         password = 'testyboi',
#         confirm_password = 'testyboi'
#     )
# except ValidationError as e:
#     print(e)