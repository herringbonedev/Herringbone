# ---------- Builder Stage ----------
FROM cgr.dev/chainguard/python:latest-dev AS builder

USER root

WORKDIR /app-root

RUN mkdir -p /python-packages

# copy requirements
COPY detectionengine/matcher/requirements.txt /tmp/requirements.txt

# copy shared modules (packaged via pyproject.toml)
COPY modules /modules

# install dependencies + internal modules
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir --target=/python-packages -r /tmp/requirements.txt && \
    python -m pip install --no-cache-dir --target=/python-packages /modules

# copy application code
COPY detectionengine/matcher/app /app-root/app


# ---------- Runtime Stage ----------
FROM cgr.dev/chainguard/python:latest

WORKDIR /app-root

COPY --from=builder /app-root /app-root
COPY --from=builder /python-packages /python-packages

USER 65532:65532

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app-root:/python-packages

EXPOSE 7003

ENTRYPOINT ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","7003"]