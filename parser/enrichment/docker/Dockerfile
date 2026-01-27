# ---------- Builder ----------
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# service deps
COPY parser/enrichment/requirements.txt /tmp/requirements.txt

# shared modules
COPY modules/modules /modules

RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --target=/python-packages -r /tmp/requirements.txt

# service source
COPY parser/enrichment/app /app

# ---------- Runtime ----------
FROM gcr.io/distroless/python3-debian12

WORKDIR /app

COPY --from=builder /app /app
COPY --from=builder /python-packages /python-packages
COPY --from=builder /modules /modules

USER 65532:65532

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/python-packages:/modules

ENTRYPOINT ["python3", "enrichment.py"]
