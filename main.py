from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import schema
from database import SessionLocal, engine
from models import Base

def get_application():
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['http://localhost:3000', 'localhost:3000'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*']
    )
    app.mount('/static', StaticFiles(directory='static'), name='static') # will replace to be served with nginx
    return app

app = get_application()

Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory='templates')

posts = [
    {
        'author': 'Ico Beltran',
        'title': 'Test Blog Post',
        'content': 'This is some test content for the test blog post. Thank you for coming to my TED Talk.',
        'date_posted': 'March 5, 2021'
    },
    {
        'author': 'Ico Beltran',
        'title': 'Test Blog Post Part 2',
        'content': 'The highly anticipated follow-up to my original test post, I hope you enjoyed this new post!',
        'date_posted': 'March 6, 2021'
    }
]

# Dependency
def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

# Main Pages
@app.get('/', response_class=HTMLResponse)
def root(request: Request):
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
@app.get('/post/new')
def new_post(request: Request):
    return templates.TemplateResponse('create_post.html', {'request': request, 'title': 'New Post'})