from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query, status, Security, File, Body
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from datetime import timedelta, datetime
from secrets import token_hex
from pathlib import Path
from slugify import slugify
import subprocess, shutil, json, os, html, filetype

import config, tasks, auth
import schema, crud
from models import User, Tag
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

    app.mount('/static', StaticFiles(directory='static'), name='static') # maybe replace to serve with nginx?
    app.mount('/tmp', StaticFiles(directory='tmp'), name='tmp')
    return app

app = get_application()

Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory='templates')
    
# Functions
def get_post_obj(db: Session, slug: str):
    obj = crud.get_post(db=db, slug=slug)
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
        response = RedirectResponse(url='/register', status_code=303)
        response.delete_cookie(key='Errors')
        response.set_cookie(key='Success', value=True, max_age=30, expires=30)
        return response
    except ValidationError as exception:
        errors = [error['msg'] for error in exception.errors()]
        error_str = ':'.join(errors)
        response = RedirectResponse(url='/register', status_code=303)
        response.delete_cookie(key='Success')
        response.set_cookie(key='Errors', value=error_str, max_age=30, expires=30)
        return response

# Users
@app.get('/users/me')
def read_current_user(user: User = Depends(auth.verify_token), db: Session = Depends(get_db)):
    # get user data from db
    return user.username

# CRUD
# Post Management
@app.get('/posts/edit/{post_id}', dependencies=[Security(auth.verify_token, scopes=['edit'])])
def edit_post(request: Request, post_id: str, db: Session = Depends(get_db)):
    tmp_dir = next(create_tmp())
    tmp_id = tmp_dir.replace('./tmp/', '')
    article, img_path, article_path, content_path = crud.get_post(db=db, post_id=post_id).values()
    with open(article_path) as f:
        article_html = f.read()

    for file in Path(content_path).iterdir():
        shutil.copy(file, Path(tmp_dir).joinpath(file.name))
    return templates.TemplateResponse('edit_exist.html', {'request': request, 'article_content': article_html, 'img_path': img_path, 'article': article, 'tmp_id': tmp_id})

@app.post('/posts/edit/{post_id}', dependencies=[Security(auth.verify_token, scopes=['edit'])])
def submit_edit(post_id: int, tmp_id: str = Body(..., embed=True), db: Session = Depends(get_db)):
    tmp_dir = Path(f'./tmp/{tmp_id}')
    with open(f'{tmp_dir}/article.config.json') as f:
        article_config = json.load(f)
    article_slug = slugify(article_config['title'], max_length=20)
    article_path = Path(f'./static/posts/{article_slug}')
    article_path.mkdir(parents=True, exist_ok=True)
    for file in tmp_dir.iterdir():
        shutil.move(file, article_path.joinpath(file.name))
    shutil.rmtree(tmp_dir)
    author_id = db.execute(select(User.id).where(User.username == article_config['author'])).scalar()
    
    data = {
        'title': article_config['title'],
        'slug': article_slug,
        'user_id': author_id,
        'description': article_config['description'],
        'image_text': article_config['imageAlt'],
        'photographer_name': article_config['photographerName'],
        'photographer_url': article_config['photographerUrl'],
        'keywords': article_config['keywords'],
        'tags': [Tag(name=tag) for tag in article_config['tags']]
    }
    crud.edit_post(db=db, post_id=post_id, data=data)
    return JSONResponse({'url': f'/posts/{article_slug}'})

@app.delete('/posts/{slug}', dependencies=[Security(auth.verify_token, scopes=['delete'])])
def del_post(slug: str, db: Session = Depends(get_db)):
    get_post_obj(db=db, slug=slug)
    crud.del_post(db=db, slug=slug)
    return {'detail': 'Post deleted', 'status_code': 204}

# Docs
@app.get('/openapi.json', dependencies=[Security(auth.verify_token, scopes=['admin'])])
def get_openapi_json():
    return JSONResponse(get_openapi(title=config.PROJECT_NAME, version=config.VERSION, routes=app.routes))

@app.get('/docs', dependencies=[Security(auth.verify_token, scopes=['admin'])])
def get_docs():
    return get_swagger_ui_html(openapi_url='/openapi.json', title='Docs')


# Editing/MD-HTML
def create_tmp():
    tmp_id = str(token_hex(8))
    tmp_dir = f'./tmp/{tmp_id}'
    Path(tmp_dir).mkdir()
    yield tmp_dir


def escape_html(file: Path, unescape: bool = False):
    with open(file, 'r+') as f:
        content = f.read()
        if unescape:
            esc_content = html.unescape(content)
        else:
            esc_content = html.escape(content, quote=False)
        f.seek(0)
        f.write(esc_content)
        f.truncate()

@app.get('/posts/edit', response_class=HTMLResponse, dependencies=[Security(auth.verify_token, scopes=['edit'])])
def search_posts(request: Request, db: Session = Depends(get_db)):
    post_list = [post.title for post in crud.get_all_posts(db=db)]
    return templates.TemplateResponse('edit_search.html', {'request': request, 'post_list': post_list})

@app.post('/posts/edit', response_class=RedirectResponse, dependencies=[Security(auth.verify_token, scopes=['edit'])])
def redir_edit(search: str = Form(...), db: Session = Depends(get_db)):
    slug = slugify(search)
    post = crud.get_post(slug=slug, db=db)['post_obj']
    return RedirectResponse(f'/posts/edit/{post.id}')

@app.get('/posts/create', response_class=HTMLResponse, dependencies=[Security(auth.verify_token, scopes=['post'])])
def upload_input(request: Request):
    return templates.TemplateResponse('upload.html', {'request': request})


@app.post('/posts/create', response_class=HTMLResponse, dependencies=[Security(auth.verify_token, scopes=['edit'])])
def upload(
    request: Request,
    article_file: bytes = File(...),
    img_file: bytes = File(...),
    title: str = Form(...),
    description: str = Form(...),
    tags: str = Form(...),
    img_alt: str = Form(...),
    pg_name: str = Form(...),
    pg_url: str = Form(...),
    user: User = Depends(auth.verify_token)
):
    tmp_dir = next(create_tmp())

    tag_list = tags.replace(' ', '').split(',')
    date = datetime.today().strftime('%Y-%m-%d')
    with open(f'{tmp_dir}/article.config.json', 'w') as f:
        json.dump({'title': title, 'description': description, 'author': user.username, 'date': date, 'tags': tag_list, 'imageAlt': img_alt, 'photographerName': pg_name, 'photographerUrl': pg_url, 'keywords': tags.replace(' ', '')},
            f, indent=4)

    img_ext = filetype.guess_extension(img_file)
    if not img_ext:
        img_ext = 'png'
    img_path = f'{tmp_dir}/headerImage.{img_ext}'
    with open(img_path, 'wb') as f:
        f.write(img_file)

    tmp_id = tmp_dir.replace('./tmp/', '')
    with open(f'{tmp_dir}/article.md', 'wb') as f:
        f.write(article_file)
    escape_html(file=(Path(f'./tmp/{tmp_id}/article.md')), unescape=True)
    cmd = f"""node -e 'require("./md-html.js").convert("{tmp_dir}")'"""
    subprocess.run(cmd, shell=True)

    with open(f'{tmp_dir}/article.html') as f:
        article_html = f.read()

    article = {
        'title': title,
        'slug': slugify(title, max_length=20),
        'date_posted': date,
        'description': description,
        'image_text': img_alt,
        'photographer_name': pg_name,
        'photographer_url': pg_url,
        'keywords': tags.replace(' ', ''),
        'tags': [Tag(name=tag) for tag in tags.replace(' ', '').split(',')]
    }
    return templates.TemplateResponse('edit.html', {'request': request, 'article_content': article_html, 'img_path': img_path, 'article': article, 'tmp_id': tmp_id, 'author': user.username})


@app.get('/edit/{tmp_id}', response_class=FileResponse, dependencies=[Security(auth.verify_token, scopes=['edit'])])
def get_article_md(tmp_id: str):
    escape_html(file=(Path(f'./tmp/{tmp_id}/article.md')))
    return FileResponse(f'./tmp/{tmp_id}/article.md')


@app.post('/edit/{tmp_id}', response_class=FileResponse, dependencies=[Security(auth.verify_token, scopes=['edit'])])
def convert_edit(tmp_id: str, article_md: bytes = File(...)):
    tmp_dir = f'./tmp/{tmp_id}'
    with open(f'{tmp_dir}/article.md', 'wb') as f:
        f.write(article_md)
    
    escape_html(file=(Path(f'./tmp/{tmp_id}/article.md')), unescape=True)
    cmd = f"""node -e 'require("./md-html.js").convert("{tmp_dir}")'"""
    subprocess.run(cmd, shell=True)
    return FileResponse(f'{tmp_dir}/article.html')


@app.post('/submit/{tmp_id}', response_class=JSONResponse, dependencies=[Security(auth.verify_token, scopes=['post'])])
def submit_article(tmp_id: str, db: Session = Depends(get_db)):
    tmp_dir = Path(f'./tmp/{tmp_id}')
    with open(f'{tmp_dir}/article.config.json') as f:
        article_config = json.load(f)
    article_slug = slugify(article_config['title'], max_length=20)
    article_path = Path(f'./static/posts/{article_slug}')
    article_path.mkdir(parents=True, exist_ok=True)
    for file in tmp_dir.iterdir():
        shutil.move(file, article_path.joinpath(file.name))
    shutil.rmtree(tmp_dir)
    author_id = db.execute(select(User.id).where(User.username == article_config['author']))
    
    data = {
        'title': article_config['title'],
        'slug': article_slug,
        'user_id': author_id,
        'description': article_config['description'],
        'image_text': article_config['imageAlt'],
        'photographer_name': article_config['photographerName'],
        'photographer_url': article_config['photographerUrl'],
        'keywords': article_config['keywords'],
        'tags': [Tag(name=tag) for tag in article_config['tags']]
    }
    crud.create_post(db=db, post=data)
    return JSONResponse({'url': f'/posts/{article_slug}'})

# Post Pages
@app.get('/posts/{slug}', response_class=HTMLResponse)
def get_post(request: Request, slug: str, db: Session = Depends(get_db)):
    article, img_path, article_path, content_path = crud.get_post(db=db, slug=slug).values()
    with open(article_path) as f:
        content = f.read()
    return templates.TemplateResponse('post.html', {'request': request, 'article': article, 'article_content': content, 'img_path': img_path})