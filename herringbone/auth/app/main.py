from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth

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

# Enterprise extensions
try:
    from app.enterprise import register_enterprise
    register_enterprise(app)
except ImportError:
    pass