from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query, status, Security, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import ValidationError
from sqlalchemy.orm import Session
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

@app.get('/posts/edit')
def edit_post():
    pass

@app.post('/posts/edit')
def submit_edit():
    pass

@app.delete('/posts/{slug}', dependencies=[Security(auth.verify_token, scopes=['delete'])])
def del_post(slug: str, db: Session = Depends(get_db)):
    get_post_obj(db=db, slug=slug)
    crud.del_post(db=db, slug=slug)
    return {'detail': 'Post deleted', 'status_code': 204}

# Post Pages
@app.get('/posts/{slug}', response_class=HTMLResponse)
def get_post(request: Request, slug: str, db: Session = Depends(get_db)):
    article_data = crud.get_post(db=db, slug=slug)
    article, img_path, content_path = article_data.values()
    with open(content_path) as f:
        content = f.read()
    return templates.TemplateResponse('post.html', {'request': request, 'article': article, 'article_content': content, 'img_path': img_path})

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


@app.get('/edit', response_class=HTMLResponse)
def upload_input(request: Request):
    return templates.TemplateResponse('upload.html', {'request': request})


@app.post('/edit', response_class=HTMLResponse)
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


@app.get('/edit/{tmp_id}', response_class=FileResponse)
def get_article_md(tmp_id: str):
    escape_html(file=(Path(f'./tmp/{tmp_id}/article.md')))
    return FileResponse(f'./tmp/{tmp_id}/article.md')


@app.post('/edit/{tmp_id}', response_class=FileResponse)
def convert_edit(tmp_id: str, article_md: bytes = File(...)):
    tmp_dir = f'./tmp/{tmp_id}'
    with open(f'{tmp_dir}/article.md', 'wb') as f:
        f.write(article_md)
    
    escape_html(file=(Path(f'./tmp/{tmp_id}/article.md')), unescape=True)
    cmd = f"""node -e 'require("./md-html.js").convert("{tmp_dir}")'"""
    subprocess.run(cmd, shell=True)
    return FileResponse(f'{tmp_dir}/article.html')


@app.post('/submit/{tmp_id}', response_class=JSONResponse)
def submit_article(tmp_id: str, db: Session = Depends(get_db), user: User = Depends(auth.verify_token)):
    tmp_dir = f'./tmp/{tmp_id}'
    article_files = os.listdir(tmp_dir)
    with open(f'{tmp_dir}/article.config.json') as f:
        article_config = json.load(f)
    article_slug = slugify(article_config['title'], max_length=20)
    article_path = f'./static/posts/{article_slug}'
    Path(article_path).mkdir(parents=True, exist_ok=True)
    for file in article_files:
        shutil.move(Path(tmp_dir).joinpath(file), Path(article_path).joinpath(file))
    shutil.rmtree(tmp_dir)
    
    data = {
        'title': article_config['title'],
        'slug': article_slug,
        'user_id': user.id,
        'description': article_config['description'],
        'image_text': article_config['imageAlt'],
        'photographer_name': article_config['photographerName'],
        'photographer_url': article_config['photographerUrl'],
        'keywords': article_config['keywords'],
        'tags': [Tag(name=tag) for tag in article_config['tags']]
    }
    crud.create_post(db=db, post=data)
    return JSONResponse({'url': f'/posts/{article_slug}'})