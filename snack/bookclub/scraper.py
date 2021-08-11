from __future__ import annotations

import os
import re

import requests
from bs4 import BeautifulSoup
from slugify import slugify
from snack.bookclub.models import Book
from sqlalchemy.orm import Session

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0"
}


async def get_book_data(db: Session, url: str):
    book_page = requests.get(url, headers=headers)
    book_page.raise_for_status()

    book_soup = BeautifulSoup(book_page.content, "html.parser")

    description_container = book_soup.find("div", id="descriptionContainer")
    description: str = description_container.find("span", id=re.compile("^freeText[0-9]")).text

    # Description clean up
    description = description.strip().replace("(back cover)", "")

    title: str = book_soup.find("h1", id="bookTitle").text.strip()
    author: str = book_soup.find("span", itemprop="name").text.strip()
    page_count = int(book_soup.find("span", itemprop="numberOfPages").text.replace(" pages", ""))
    image_url: str = book_soup.find("img", id="coverImage")["src"]

    os.makedirs("static/covers/", exist_ok=True)
    image_path = f"static/covers/{slugify(title, max_length=30, word_boundary=True)}.jpg"
    with requests.get(image_url, stream=True, headers=headers) as response:
        with open(image_path, "wb") as file:
            file.write(response.content)

    book_info: dict[str, str | int] = {
        "title": title,
        "author": author,
        "page_count": page_count,
        "image": image_path.removeprefix("static"),
        "description": description,
    }

    return book_info
