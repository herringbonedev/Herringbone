from fastapi import FastAPI
from routers import ruleset

app = FastAPI()

app.include_router(ruleset.router)
