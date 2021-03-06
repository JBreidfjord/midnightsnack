from fastapi import FastAPI

app = FastAPI()

@app.get('/')
def root():
    return 'Home Page'

@app.get('/about')
def about():
    return 'About Page'