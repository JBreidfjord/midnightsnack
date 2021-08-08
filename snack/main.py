import html
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from secrets import token_hex
from typing import Optional

import filetype
from fastapi import Body, Depends, FastAPI, File, Form, Query, Request, Security, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from slugify import slugify
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from snack import auth, config, crud, schema
from snack.database import Base, SessionLocal, engine
from snack.dependencies import get_db, get_post_obj
from snack.models import Tag, User


def get_application():
    app = FastAPI(
        title=config.PROJECT_NAME,
        version=config.VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory="static"), name="static")
    return app


app = get_application()

Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="templates")

# Exception Handlers
@app.exception_handler(RequestValidationError)
@app.exception_handler(Exception)
@app.exception_handler(HTTPException)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    try:
        if exc.status_code == 401:
            response = RedirectResponse(url="/login", status_code=303)
            response.set_cookie(key="Errors", value=True, max_age=30, expires=30)
            return response
        if exc.status_code == 403:
            return templates.TemplateResponse(
                "403.html", {"request": request, "exc": exc}, status_code=403
            )
        if exc.status_code == 404:
            return templates.TemplateResponse(
                "404.html", {"request": request, "exc": exc}, status_code=404
            )
        if exc.status_code == 422:
            return templates.TemplateResponse(
                "422.html", {"request": request, "exc": exc}, status_code=422
            )
        if exc.status_code == 500:
            return templates.TemplateResponse(
                "500.html", {"request": request, "exc": exc}, status_code=500
            )
        else:
            return templates.TemplateResponse(
                "error.html", {"request": request, "exc": exc}, status_code=exc.status_code
            )
    except AttributeError:
        return templates.TemplateResponse(
            "500.html", {"request": request, "exc": exc}, status_code=500
        )


# Main Pages
@app.get("/", response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)):
    posts = crud.get_recent_posts(db=db, limit=10)
    return templates.TemplateResponse(
        "home.html", {"request": request, "title": "Home", "posts": posts}
    )


@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request, "title": "About"})


@app.get("/contact", response_class=HTMLResponse)
def contact(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request, "title": "Contact"})


# Authentication
@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    if request.cookies.get("Authorization"):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "title": "Login",})


@app.post("/login", response_class=RedirectResponse)
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    user = auth.authenticate_user(
        username=form_data.username, password=form_data.password, db=SessionLocal()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username, "scopes": user.scopes}, expires_delta=access_token_expires
    )
    response = RedirectResponse(url="/", status_code=303)
    cookie_expires = config.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.delete_cookie(key="Errors")
    response.set_cookie(
        key="Authorization",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=True,
        max_age=cookie_expires,
        expires=cookie_expires,
    )
    response.set_cookie(
        key="User", value=user.username, max_age=cookie_expires, expires=cookie_expires
    )
    response.set_cookie(
        key="Scopes", value=user.scopes, max_age=cookie_expires, expires=cookie_expires
    )
    return response


@app.get("/logout", response_class=RedirectResponse)
def logout(response: Response):
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="Authorization")
    response.delete_cookie(key="User")
    response.delete_cookie(key="Scopes")
    return response


@app.get("/register", response_class=HTMLResponse)
def register(request: Request):
    if request.cookies.get("Authorization"):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request, "title": "Register"})


@app.post("/register", response_class=RedirectResponse)
def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    verify_data = {
        "username": username,
        "email": email,
        "password": password,
        "confirm_password": confirm_password,
    }
    hashed_password = auth.get_password_hash(password)
    user_data = {"username": username, "email": email, "password": hashed_password}
    try:
        schema.UserCreate(**verify_data)
        user = User(**user_data)
        db = SessionLocal()
        db.add(user)
        db.commit()
        response = RedirectResponse(url="/register", status_code=303)
        response.delete_cookie(key="Errors")
        response.set_cookie(key="Success", value=user.username, max_age=30, expires=30)
        return response
    except ValidationError as exception:
        errors = [error["msg"] for error in exception.errors()]
        error_str = ":".join(errors)
        response = RedirectResponse(url="/register", status_code=303)
        response.delete_cookie(key="Success")
        response.set_cookie(key="Errors", value=error_str, max_age=30, expires=30)
        return response


# Users
@app.get("/users/{username}", response_class=HTMLResponse)
def read_current_user(request: Request, username: str, db: Session = Depends(get_db)):
    user = crud.get_user(db=db, username=username)
    return templates.TemplateResponse("user.html", {"request": request, "user": user})


@app.get("/posts/all", response_class=HTMLResponse)
def get_all_posts(request: Request, db: Session = Depends(get_db)):
    posts = crud.get_all_posts(db=db)
    return templates.TemplateResponse("postlist.html", {"request": request, "posts": posts})


# CRUD
# Post Management
@app.delete("/posts/{slug}", dependencies=[Security(auth.verify_token, scopes=["delete"])])
def del_post(slug: str, db: Session = Depends(get_db)):
    get_post_obj(db=db, slug=slug)
    crud.del_post(db=db, slug=slug)
    return {"detail": "Post deleted", "status_code": 204}


# Docs/Admin
@app.get(
    "/admin",
    response_class=HTMLResponse,
    dependencies=[Security(auth.verify_token, scopes=["admin"])],
)
async def admin(request: Request, db: Session = Depends(get_db)):
    users = sorted(crud.get_all_users(db=db), key=lambda x: x.username)
    return templates.TemplateResponse("admin.html", {"request": request, "users": users})


@app.post(
    "/admin/scopes",
    response_class=RedirectResponse,
    dependencies=[Security(auth.verify_token, scopes=["admin"])],
)
async def update_scopes(request: Request, user: str = Form(...), db: Session = Depends(get_db)):
    formdata = await request.form()
    scopes = [scope for scope in formdata if scope != "user"]
    crud.update_scopes(username=user, scopes=scopes, db=db)
    return RedirectResponse("/admin", status_code=303)


@app.get("/openapi.json", dependencies=[Security(auth.verify_token, scopes=["admin"])])
def get_openapi_json():
    return JSONResponse(
        get_openapi(title=config.PROJECT_NAME, version=config.VERSION, routes=app.routes)
    )


@app.get("/docs", dependencies=[Security(auth.verify_token, scopes=["admin"])])
def get_docs():
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Docs")


# Editing/MD-HTML
def create_tmp():
    tmp_id = str(token_hex(8))
    tmp_dir = f"./static/tmp/{tmp_id}"
    Path(tmp_dir).mkdir(parents=True, exist_ok=False)
    yield tmp_dir


def escape_html(file: Path, unescape: bool = False):
    with open(file, "r+") as f:
        content = f.read()
        if unescape:
            esc_content = html.unescape(content)
        else:
            esc_content = html.escape(content, quote=False)
        f.seek(0)
        f.write(esc_content)
        f.truncate()


@app.get(
    "/posts/edit",
    response_class=HTMLResponse,
    dependencies=[Security(auth.verify_token, scopes=["edit"])],
)
def search_posts(request: Request, db: Session = Depends(get_db)):
    posts = [
        {"title": post.title.replace('"', "'"), "id": post.id} for post in crud.get_all_posts(db=db)
    ]
    posts = sorted(posts, key=lambda x: x["title"])
    posts = json.dumps(posts)
    return templates.TemplateResponse("edit_search.html", {"request": request, "posts": posts})


@app.post(
    "/posts/edit",
    response_class=RedirectResponse,
    dependencies=[Security(auth.verify_token, scopes=["edit"])],
)
def redir_edit(search: str = Form(...), db: Session = Depends(get_db)):
    slug = slugify(search)
    post = crud.get_post(slug=slug, db=db)
    return RedirectResponse(f"/posts/edit/{post.id}")


@app.get("/posts/edit/{post_id}", dependencies=[Security(auth.verify_token, scopes=["edit"])])
def edit_post(request: Request, post_id: int, db: Session = Depends(get_db)):
    tmp_dir = next(create_tmp())
    tmp_id = tmp_dir.replace("./static/tmp/", "")
    article, img_path, article_path, content_path = crud.get_post_data(
        db=db, post_id=post_id
    ).values()
    with open(article_path) as f:
        article_html = f.read()

    for file in Path(content_path).iterdir():
        shutil.copy(file, Path(tmp_dir).joinpath(file.name))
    return templates.TemplateResponse(
        "edit_exist.html",
        {
            "request": request,
            "article_content": article_html,
            "img_path": img_path,
            "article": article,
            "tmp_id": tmp_id,
        },
    )


@app.post("/posts/edit/{post_id}", dependencies=[Security(auth.verify_token, scopes=["edit"])])
def submit_edit(post_id: int, tmp_id: str = Body(..., embed=True), db: Session = Depends(get_db)):
    tmp_dir = Path(f"./static/tmp/{tmp_id}")
    with open(f"{tmp_dir}/article.config.json") as f:
        article_config = json.load(f)
    article_slug = slugify(article_config["title"], max_length=20)
    article_path = Path(f"./static/posts/{article_slug}")
    article_path.mkdir(parents=True, exist_ok=True)
    for file in tmp_dir.iterdir():
        shutil.move(file, article_path.joinpath(file.name))
    shutil.rmtree(tmp_dir)
    return JSONResponse({"url": f"/posts/{article_slug}"})


@app.get(
    "/posts/edit/{post_id}/info",
    response_class=HTMLResponse,
    dependencies=[Security(auth.verify_token, scopes=["edit"])],
)
def edit_post_info(request: Request, post_id: int, db: Session = Depends(get_db)):
    path = crud.get_post_data(db=db, post_id=post_id)["content_path"]
    config_path = Path(path).joinpath("article.config.json")
    with open(config_path) as f:
        config = json.load(f)
    return templates.TemplateResponse(
        "edit_info.html", {"request": request, "config": config, "post_id": post_id}
    )


@app.post(
    "/posts/edit/{post_id}/info",
    response_class=RedirectResponse,
    dependencies=[Security(auth.verify_token, scopes=["edit"])],
)
def update_post_info(
    post_id: int,
    db: Session = Depends(get_db),
    img_file: Optional[bytes] = File(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    img_alt: Optional[str] = Form(None),
    pg_name: Optional[str] = Form(None),
    pg_url: Optional[str] = Form(None),
):
    post_data = crud.get_post_data(db=db, post_id=post_id)
    img_path = post_data["img_path"]
    content_path = post_data["content_path"]

    img_path = Path("./static").joinpath(img_path)
    if img_file:
        img_ext = filetype.guess_extension(img_file)
        if not img_ext:
            img_ext = "png"
        os.remove(img_path)
        img_path = Path(content_path).joinpath(f"headerImage.{img_ext}")
        with open(img_path, "wb") as f:
            f.write(img_file)

    input_data = {
        "title": title,
        "description": description,
        "imageAlt": img_alt,
        "photographerName": pg_name,
        "photographerUrl": pg_url,
    }

    config_path = Path(content_path).joinpath("article.config.json")
    with open(config_path) as f:
        config = json.load(f)
    old_slug = slugify(config["title"], max_length=20)

    tag_list = []
    if tags:
        tag_list = tags.replace(" ", "").split(",")
        config["tags"] = tag_list
        config["keywords"] = tags.replace(" ", "")

    for item in input_data.items():
        if item[1]:  # 1st index is value, 0th is key
            config[item[0]] = item[1]

    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)

    slug = slugify(config["title"], max_length=20)
    new_path = Path(str(content_path).replace(old_slug, slug))
    os.rename(content_path, new_path)

    data = {
        "title": config["title"],
        "slug": slug,
        "description": config["description"],
        "image_text": config["imageAlt"],
        "photographer_name": config["photographerName"],
        "photographer_url": config["photographerUrl"],
        "keywords": config["keywords"],
    }
    tags = [Tag(name=tag.lower()) for tag in tag_list]
    crud.edit_post(db=db, post_id=post_id, data=data, tags=tags)
    return RedirectResponse(
        url=f"/posts/{slugify(config['title'], max_length=20)}", status_code=303
    )


@app.get(
    "/posts/create",
    response_class=HTMLResponse,
    dependencies=[Security(auth.verify_token, scopes=["post"])],
)
def upload_input(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.post(
    "/posts/create",
    response_class=HTMLResponse,
    dependencies=[Security(auth.verify_token, scopes=["edit"])],
)
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
    user: User = Depends(auth.verify_token),
):
    tmp_dir = next(create_tmp())

    tag_list = tags.replace(" ", "").split(",")
    date = datetime.today().strftime("%Y-%m-%d")
    with open(f"{tmp_dir}/article.config.json", "w") as f:
        json.dump(
            {
                "title": title,
                "description": description,
                "author": user.username,
                "date": date,
                "tags": tag_list,
                "imageAlt": img_alt,
                "photographerName": pg_name,
                "photographerUrl": pg_url,
                "keywords": tags.replace(" ", ""),
            },
            f,
            indent=4,
        )

    tmp_id = tmp_dir.replace("./static/tmp/", "")

    img_ext = filetype.guess_extension(img_file)
    if not img_ext:
        img_ext = "png"
    img_path = f"{tmp_dir}/headerImage.{img_ext}"
    with open(img_path, "wb") as f:
        f.write(img_file)

    with open(f"{tmp_dir}/article.md", "wb") as f:
        f.write(article_file)
    escape_html(file=(Path(f"{tmp_dir}/article.md")), unescape=True)

    # This is absurd
    cmd = f"""node -e 'require("static/src/md-html.js").convert("{tmp_dir}")'"""
    subprocess.run(cmd, shell=True)

    with open(f"{tmp_dir}/article.html") as f:
        article_html = f.read()

    article = {
        "title": title,
        "slug": slugify(title, max_length=20),
        "date_posted": date,
        "description": description,
        "image_text": img_alt,
        "photographer_name": pg_name,
        "photographer_url": pg_url,
        "keywords": tags.replace(" ", ""),
        "tags": [Tag(name=tag.lower()) for tag in tags.replace(" ", "").split(",")],
    }
    img_path = f"/tmp/{tmp_id}/headerImage.{img_ext}"
    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "article_content": article_html,
            "img_path": img_path,
            "article": article,
            "tmp_id": tmp_id,
            "author": user.username,
        },
    )


@app.get(
    "/edit/{tmp_id}",
    response_class=FileResponse,
    dependencies=[Security(auth.verify_token, scopes=["edit"])],
)
def get_article_md(tmp_id: str):
    escape_html(file=(Path(f"./static/tmp/{tmp_id}/article.md")))
    return FileResponse(f"./static/tmp/{tmp_id}/article.md")


@app.post(
    "/edit/{tmp_id}",
    response_class=FileResponse,
    dependencies=[Security(auth.verify_token, scopes=["edit"])],
)
def convert_edit(tmp_id: str, article_md: bytes = File(...)):
    tmp_dir = f"./static/tmp/{tmp_id}"
    with open(f"{tmp_dir}/article.md", "wb") as f:
        f.write(article_md)

    escape_html(file=(Path(f"./static/tmp/{tmp_id}/article.md")), unescape=True)

    # This is absurd
    cmd = f"""node -e 'require("static/src/md-html.js").convert("{tmp_dir}")'"""
    subprocess.run(cmd, shell=True)
    return FileResponse(f"{tmp_dir}/article.html")


@app.post(
    "/edit/{tmp_id}/submit",
    response_class=JSONResponse,
    dependencies=[Security(auth.verify_token, scopes=["post"])],
)
def submit_article(tmp_id: str, db: Session = Depends(get_db)):
    tmp_dir = Path(f"./static/tmp/{tmp_id}")
    with open(f"{tmp_dir}/article.config.json") as f:
        article_config = json.load(f)
    article_slug = slugify(article_config["title"], max_length=20)
    article_path = Path(f"./static/posts/{article_slug}")
    article_path.mkdir(parents=True, exist_ok=True)
    for file in tmp_dir.iterdir():
        shutil.move(file, article_path.joinpath(file.name))
    shutil.rmtree(tmp_dir)
    author_id = db.execute(
        select(User.id).where(User.username == article_config["author"])
    ).scalar()

    data = {
        "title": article_config["title"],
        "slug": article_slug,
        "user_id": author_id,
        "date_posted": datetime.today().strftime("%Y-%m-%d"),
        "description": article_config["description"],
        "image_text": article_config["imageAlt"],
        "photographer_name": article_config["photographerName"],
        "photographer_url": article_config["photographerUrl"],
        "keywords": article_config["keywords"],
    }
    tags = [Tag(name=tag.lower()) for tag in article_config["tags"]]
    crud.create_post(db=db, post=data, tags=tags)
    return JSONResponse({"url": f"/posts/{article_slug}"})


# Post Pages
@app.get("/posts/{slug}", response_class=HTMLResponse)
def get_post(request: Request, slug: str, db: Session = Depends(get_db)):
    post = crud.get_post_data(db=db, slug=slug)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    article, img_path, article_path, content_path = post.values()
    with open(article_path) as f:
        content = f.read()
    return templates.TemplateResponse(
        "post.html",
        {"request": request, "article": article, "article_content": content, "img_path": img_path},
    )


@app.get("/tags", response_class=HTMLResponse)
def get_all_tags(request: Request, db: Session = Depends(get_db)):
    tags = crud.get_all_tags(db=db)
    return templates.TemplateResponse("taglist.html", {"request": request, "tags": tags})


@app.get("/tags/{tag}", response_class=HTMLResponse)
def get_tags(request: Request, tag: str, db: Session = Depends(get_db)):
    tag = db.execute(select(Tag).where(Tag.name == tag)).scalar()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    else:
        return templates.TemplateResponse("tag.html", {"request": request, "tag": tag})

