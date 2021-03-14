from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Request, status
from typing import Optional
from fastapi.openapi.models import OAuthFlows
from fastapi.security import OAuth2
from fastapi.security.utils import get_authorization_scheme_param
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import ValidationError

import schema, config
from models import User
from dependencies import get_db

# OAuth2
class OAuth2PasswordBearerCookie(OAuth2):
    def __init__(
        self,
        tokenUrl: str,
        scheme_name: str = None,
        scopes: dict = None,
        auto_error: bool = True
    ):
        if not scopes:
            scopes = {}
        flows = OAuthFlows(password={'tokenUrl': tokenUrl, 'scopes': scopes})
        super().__init__(flows=flows, scheme_name=scheme_name, auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[str]:
        cookie_authorization: str = request.cookies.get('Authorization')

        cookie_scheme, cookie_param = get_authorization_scheme_param(cookie_authorization)

        if cookie_scheme.lower() == 'bearer':
            authorization = True
            scheme = cookie_scheme
            param = cookie_param

        else:
            authorization = False

        if not authorization or scheme.lower() != 'bearer':
            if self.auto_error:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Not authenticated')
            else:
                return None
        return param

oauth2_scheme = OAuth2PasswordBearerCookie(tokenUrl='/login')

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db: Session, username: str):
    db_user = db.execute(select(User).where(User.username == username)).scalar()
    user = schema.UserInfo.from_orm(db_user)
    return user

def authenticate_user(db: Session, username: str, password: str):
    user = get_user(db=db, username=username)
    if not user:
        return False
    if not verify_password(plain_password=password, hashed_password=user.password):
        return False
    return user

# Tokens
def create_access_token(data: schema.UserInfo, expires_delta: Optional[timedelta] = None):
    to_encode = data
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(to_encode, str(config.SECRET_KEY), algorithm=config.ALGORITHM)
    return encoded_jwt

def verify_token(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Could not validate credentials',
        headers={'WWW-Authenticate': 'Bearer'}
    )
    try:
        payload = jwt.decode(token, str(config.SECRET_KEY), algorithms=[config.ALGORITHM])
        try:
            user = db.execute(select(User).where(User.username == payload.get('sub'))).scalar()
            return user
        except ValidationError:
            raise credentials_exception
    except JWTError:
        raise credentials_exception