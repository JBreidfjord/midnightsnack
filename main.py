from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query, status, Cookie
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from urllib.parse import quote
from datetime import timedelta
import json

import config, tasks, auth
import schema, crud
from models import User, Post
from database import SessionLocal, engine, Base
from dependencies import get_db

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
    
# Functions
def get_post_obj(db: Session, post_id: int):
    obj = crud.get_post(db=db, post_id=post_id)
    if obj is None:
        raise HTTPException(status_code=404, detail='Post not found')
    return obj

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
@app.get('/login', response_class=HTMLResponse)
def login(request: Request, errors: Optional[List[str]] = Query(None), success: Optional[bool] = Query(None)):
    return templates.TemplateResponse('login.html', {'request': request, 'title': 'Login', 'errors': errors, 'success': success})

@app.post('/login', response_class=RedirectResponse)
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    user = auth.authenticate_user(username=form_data.username, password=form_data.password, db=SessionLocal())
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect username or password',
            headers={'WWW-Authenticate': 'Bearer'}
        )
    access_token_expires = timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={'sub': user.username}, expires_delta=access_token_expires
    )
    response = RedirectResponse(url='/', status_code=303)
    response.set_cookie(key='Authorization', value=f'Bearer {access_token}', httponly=True, secure=True)
    return response

@app.get('/logout', response_class=RedirectResponse)
def logout(response: Response):
    response = RedirectResponse(url='/', status_code=303)
    response.delete_cookie(key='Authorization')
    return response

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
def read_current_user(user: User = Depends(auth.verify_token), db: Session = Depends(get_db)):
    return user.username

# CRUD
# Post Management
@app.get('/posts/new', response_class=HTMLResponse)
def new_post(request: Request, token: str = Depends(auth.oauth2_scheme)):
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