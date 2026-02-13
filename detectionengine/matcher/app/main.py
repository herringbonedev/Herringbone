from fastapi import FastAPI
from app.routers import matcher

app = FastAPI()

app.include_router(matcher.router)