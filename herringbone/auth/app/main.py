from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    auth,
    users,
    services,
    ingestion
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core router
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(services.router)
app.include_router(ingestion.router)

# Enterprise extensions
try:
    from app.enterprise import register_enterprise
    register_enterprise(app)
except ImportError:
    print("Core Mode.")