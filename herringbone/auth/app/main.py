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


def print_loaded_routes(app: FastAPI):
    print("Loaded FastAPI routes:")
    for route in sorted(app.routes, key=lambda r: getattr(r, "path", "")):
        path = getattr(route, "path", "")
        methods = sorted(getattr(route, "methods", []) or [])
        name = getattr(route, "name", "")
        print(f"{','.join(methods):20} {path} -> {name}")

print_loaded_routes(app)