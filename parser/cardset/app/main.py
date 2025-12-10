from fastapi import FastAPI
from routers import cardset

app = FastAPI()

app.include_router(cardset.router)
