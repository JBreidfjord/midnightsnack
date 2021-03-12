from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from typing import List, Optional
from urllib.parse import quote
from datetime import datetime
import json

import config, tasks, auth
import schema, crud
from models import User, Post
from database import SessionLocal, engine, Base

def get_application():
    app = FastAPI(title=config.PROJECT_NAME, version=config.VERSION)
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['http://localhost:3000', 'localhost:3000'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*']
    )

    app.add_event_handler('startup', tasks.create_start_app_handler(app))
    app.add_event_handler('shutdown', tasks.create_stop_app_handler(app))

    app.mount('/static', StaticFiles(directory='static'), name='static') # will replace to be served with nginx
    return app

app = get_application()

Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory='templates')

# OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='token')

def decode_token(token):
    return schema.UserBase()

def hash_password(password: str):
    return 'hash' + password

# Dependency
def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Could not validate credentials',
        headers={'WWW-Authenticate', 'Bearer'}
    )
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        username: str = payload.get('sub')
        if username is None:
            raise credentials_exception
        token_data = schema.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = auth.get_user(db=get_db(), username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

# Functions
def get_post_obj(db: Session, post_id: int):
    obj = crud.get_post(db=db, post_id=post_id)
    if obj is None:
        raise HTTPException(status_code=404, detail='Post not found')
    return obj

def get_current_active_user(current_user: schema.UserBase = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail='Inactive user')
    return current_user
    

# Main Pages
@app.get('/', response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)):
    posts = crud.get_all_posts(db=db)
    return templates.TemplateResponse('home.html', {'request': request, 'title': 'Home', 'posts': posts})

@app.get('/about', response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse('about.html', {'request': request, 'title': 'About'})

@app.get('/contact', response_class=HTMLResponse)
def contact(request: Request):
    return templates.TemplateResponse('contact.html', {'request': request, 'title': 'Contact'})

# Authentication
@app.post('/token')
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = auth.authenticate_user(username=form_data.username, password=form_data.password, db=SessionLocal())
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect username or password',
            headers={'WWW-Authenticate': 'Bearer'}
        )
    access_token_expires = datetime.timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={'sub': user.username}, expires_delta=access_token_expires
    )
    return {'access_token': access_token, 'token_type': 'bearer'}

@app.get('/login', response_class=HTMLResponse)
def login(request: Request, errors: Optional[List[str]] = Query(None), success: Optional[bool] = Query(None)):
    return templates.TemplateResponse('login.html', {'request': request, 'title': 'Login', 'errors': errors, 'success': success})

@app.post('/login')
def login(username: str = Form(...), password: str = Form(...)):
    pass

@app.get('/register', response_class=HTMLResponse)
def register(request: Request, errors: Optional[List[str]] = Query(None), success: Optional[bool] = Query(None)):
    return templates.TemplateResponse('register.html', {'request': request, 'title': 'Register', 'errors': errors, 'success': success})

@app.post('/register', response_class=RedirectResponse)
def register(username: str = Form(...), email: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):
    verify_data = {'username': username, 'email': email, 'password': password, 'confirm_password': confirm_password}
    hashed_password = auth.get_password_hash(password)
    user_data = {'username': username, 'email': email, 'password': hashed_password}
    try:
        schema.UserCreate(**verify_data)
        user = User(**user_data)
        db = SessionLocal()
        db.add(user)
        db.commit()
        return RedirectResponse(url=f'/register?success=True', status_code=303)
    except ValidationError as exception:
        errors = [f"errors={quote(error['msg'])}" for error in exception.errors()]
        query = '?' + '&'.join(errors)
        return RedirectResponse(url=f'/register{query}', status_code=303)

# Users
@app.get('/users/me')
def read_current_user(current_user: schema.UserBase = Depends(get_current_active_user)):
    return current_user

# CRUD
# Post Management
@app.get('/posts/new', response_class=HTMLResponse)
def new_post(request: Request, token: str = Depends(oauth2_scheme)):
    return templates.TemplateResponse('create_post.html', {'request': request, 'title': 'New Post', 'current_user': 1})

@app.post('/posts/new', response_model=schema.PostInfo)
def submit_post(title: str = Form(...), post_content: str = Form(...), user_id: int = Form(...), db: Session = Depends(get_db)):
    post = {'title': title, 'content': post_content, 'user_id': user_id}
    return crud.create_post(db=db, post=post)

@app.delete('/posts/{post_id}')
def del_post(post_id: int, db: Session = Depends(get_db)):
    get_post_obj(db=db, post_id=post_id)
    crud.del_post(db=db, post_id=post_id)
    return {'detail': 'Post deleted', 'status_code': 204}

# Post Pages
@app.get('/posts/{post_id}', response_class=HTMLResponse)
def get_post(request: Request, post_id: int, db: Session = Depends(get_db)):
    post = crud.get_post(db=db, post_id=post_id)
    return templates.TemplateResponse('post.html', {'request': request, 'title': post.title, 'post': post})