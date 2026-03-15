# ---------- Builder Stage ----------
FROM cgr.dev/chainguard/python:latest-dev AS builder

USER root

WORKDIR /app-root

RUN mkdir -p /python-packages

# copy requirements
COPY detectionengine/detector/requirements.txt /tmp/requirements.txt

# copy shared modules (packaged via pyproject.toml)
COPY modules /modules

# install dependencies + internal modules
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir --target=/python-packages -r /tmp/requirements.txt && \
    python -m pip install --no-cache-dir --target=/python-packages /modules

# copy application code
COPY detectionengine/detector/app /app-root/app


# ---------- Runtime Stage ----------
FROM cgr.dev/chainguard/python:latest

WORKDIR /app-root

COPY --from=builder /app-root /app-root
COPY --from=builder /python-packages /python-packages

USER 65532:65532

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app-root:/python-packages

ENTRYPOINT ["python","-m","app.main"]