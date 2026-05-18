import os
import uvicorn
from fastapi import FastAPI
from app.routers import extractor


app = FastAPI()
app.include_router(extractor.router)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("EXTRACTOR_HOST", "0.0.0.0"),
        port=int(os.environ.get("EXTRACTOR_PORT", "7006")),
        workers=int(os.environ.get("EXTRACTOR_UVICORN_WORKERS", "1")),
        access_log=os.environ.get("EXTRACTOR_ACCESS_LOG", "false").lower() == "true",
        log_level=os.environ.get("EXTRACTOR_LOG_LEVEL", "info"),
    )