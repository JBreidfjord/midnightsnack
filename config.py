from starlette.config import Config
from starlette.datastructures import Secret

config = Config('.env')

PROJECT_NAME = 'Blog'
VERSION = '0.0.1'
API_PREFIX = ''

SECRET_KEY = config('SECRET_KEY', cast=Secret, default='CHANGEME')
ALGORITHM = config('ALGORITHM', cast=str)
ACCESS_TOKEN_EXPIRE_MINUTES = config('ACCESS_TOKEN_EXPIRE_MINUTES', cast=int, default=15)

POSTGRES_USER = config('POSTGRES_USER', cast=str)
POSTGRES_PASSWORD = config('POSTGRES_PASSWORD', cast=Secret)
POSTGRES_SERVER = config('POSTGRES_SERVER', cast=str, default='db')
POSTGRES_PORT = config('POSTGRES_PORT', cast=str, default='5432')
POSTGRES_DB = config('POSTGRES_DB', cast=str)

DATABASE_URL = f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}'