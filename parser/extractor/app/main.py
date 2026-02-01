from fastapi import FastAPI
from app.routers import extractor

app = FastAPI()

app.include_router(extractor.router)
