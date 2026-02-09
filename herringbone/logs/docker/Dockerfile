# ---------- Builder Stage ----------
FROM python:3.11-slim AS builder

WORKDIR /app-root

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# copy requirements
COPY herringbone/logs/requirements.txt /tmp/requirements.txt

# copy shared modules (packaged via pyproject.toml)
COPY modules /modules

# install dependencies + internal modules
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --target=/python-packages -r /tmp/requirements.txt && \
    pip install --no-cache-dir --target=/python-packages /modules

# copy application code
COPY herringbone/logs/app /app-root/app


# ---------- Runtime Stage ----------
FROM gcr.io/distroless/python3-debian12

WORKDIR /app-root

COPY --from=builder /app-root /app-root
COPY --from=builder /python-packages /python-packages

USER 65532:65532

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app-root:/python-packages


EXPOSE 7010

ENTRYPOINT ["python3","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","7010"]
