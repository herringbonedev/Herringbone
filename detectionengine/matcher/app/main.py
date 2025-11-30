from fastapi import FastAPI
from routers import matcher

app = FastAPI()

app.include_router(matcher.router)