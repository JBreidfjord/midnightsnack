from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query, status, Security
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from datetime import timedelta
import json

import config, tasks, auth
import schema, crud
from models import User, Post
from database import SessionLocal, engine, Base
from dependencies import get_db

def get_application():
    app = FastAPI(title=config.PROJECT_NAME, version=config.VERSION, docs_url=None, redoc_url=None, openapi_url=None)
    
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
        data={'sub': user.username, 'scopes': user.scopes}, expires_delta=access_token_expires
    )
    response = RedirectResponse(url='/', status_code=303)
    cookie_expires = config.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(key='Authorization', value=f'Bearer {access_token}', httponly=True, secure=True, max_age=cookie_expires, expires=cookie_expires)
    return response

@app.get('/logout', response_class=RedirectResponse)
def logout(response: Response):
    response = RedirectResponse(url='/', status_code=303)
    response.delete_cookie(key='Authorization')
    return response

@app.get('/register', response_class=HTMLResponse)
def register(request: Request):
    return templates.TemplateResponse('register.html', {'request': request, 'title': 'Register'})

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
        response = RedirectResponse(url=f'/register', status_code=303)
        response.delete_cookie(key='Errors')
        response.set_cookie(key='Success', value=True, max_age=30, expires=30)
        return response
    except ValidationError as exception:
        errors = [error['msg'] for error in exception.errors()]
        error_str = ':'.join(errors)
        response = RedirectResponse(url=f'/register', status_code=303)
        response.delete_cookie(key='Success')
        response.set_cookie(key='Errors', value=error_str, max_age=30, expires=30)
        return response

# Users
@app.get('/users/me')
def read_current_user(user: User = Depends(auth.verify_token), db: Session = Depends(get_db)):
    return user.username

# CRUD
# Post Management
@app.get('/posts/new', response_class=HTMLResponse, dependencies=[Security(auth.verify_token, scopes=['post'])])
def new_post(request: Request):
    return templates.TemplateResponse('create_post.html', {'request': request, 'title': 'New Post'})

@app.post('/posts/new', response_model=schema.PostInfo)
def submit_post(title: str = Form(...), post_content: str = Form(...), db: Session = Depends(get_db), user: User = Security(auth.verify_token, scopes=['post'])):
    post = {'title': title, 'content': post_content, 'user_id': user.id}
    return crud.create_post(db=db, post=post)

@app.delete('/posts/{post_id}', dependencies=[Security(auth.verify_token, scopes=['delete'])])
def del_post(post_id: int, db: Session = Depends(get_db)):
    get_post_obj(db=db, post_id=post_id)
    crud.del_post(db=db, post_id=post_id)
    return {'detail': 'Post deleted', 'status_code': 204}

# Post Pages
@app.get('/posts/{post_id}', response_class=HTMLResponse)
def get_post(request: Request, post_id: int, db: Session = Depends(get_db)):
    post = crud.get_post(db=db, post_id=post_id)
    return templates.TemplateResponse('post.html', {'request': request, 'title': post.title, 'post': post})

# Docs
@app.get('/openapi.json', dependencies=[Security(auth.verify_token, scopes=['admin'])])
def get_openapi_json():
    return JSONResponse(get_openapi(title=config.PROJECT_NAME, version=config.VERSION, routes=app.routes))

@app.get('/docs', dependencies=[Security(auth.verify_token, scopes=['admin'])])
def get_docs():
    return get_swagger_ui_html(openapi_url='/openapi.json', title='Docs')