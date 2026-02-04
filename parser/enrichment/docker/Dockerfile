# ---------- Builder Stage ----------
FROM python:3.11-slim AS builder

WORKDIR /app-root

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# copy requirements
COPY parser/enrichment/requirements.txt /tmp/requirements.txt
COPY parser/cardset/requirements-internal.txt /tmp/requirements-internal.txt

# copy shared modules
COPY modules /modules

# install dependencies into controlled location
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --target=/python-packages -r /tmp/requirements.txt && \
    pip install --no-cache-dir --target=/python-packages -r /tmp/requirements-internal.txt

# copy app as a top-level package
COPY parser/enrichment/app /app-root/app


# ---------- Runtime Stage ----------
FROM gcr.io/distroless/python3-debian12

WORKDIR /app-root

COPY --from=builder /app-root /app-root
COPY --from=builder /python-packages /python-packages
COPY --from=builder /modules /modules

USER 65532:65532

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app-root:/python-packages:/modules

ENTRYPOINT ["python3", "-m", "app.enrichment"]
