from typing import Any
from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import json

import config, tasks

import schema, crud
from database import SessionLocal, engine
from models import Base

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

current_user_id = 1 # add way for create_post to know current user

# Dependency
def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

# Main Pages
@app.get('/', response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)):
    posts = crud.get_all_posts(db=db)
    return templates.TemplateResponse('home.html', {'request': request, 'posts': posts})

@app.get('/about', response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse('about.html', {'request': request, 'title': 'About'})

# Registration --- Needs to be fixed and finished later ---
@app.get('/register', response_class=HTMLResponse)
def register_get(request: Request):
    form = schema.UserBase()
    return templates.TemplateResponse('register.html', {'request': request, 'title': 'Register', 'form': form})

@app.post('/register', response_model=schema.UserBase)
def register_post(form_data: schema.UserCreate = Form(...)):
    return form_data

# CRUD
@app.get('/post/new', response_class=HTMLResponse)
def new_post(request: Request):
    return templates.TemplateResponse('create_post.html', {'request': request, 'title': 'New Post', 'current_user': 1})

@app.post('/post/new', response_model=schema.PostInfo)
def submit_post(title: str = Form(...), post_content: str = Form(...), user_id: int = Form(...), db: Session = Depends(get_db)):
    post = {'title': title, 'content': post_content, 'user_id': user_id}
    return crud.create_post(db=db, post=post)