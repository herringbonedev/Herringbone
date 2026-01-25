# ---------- Builder Stage ----------
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY ../requirements.txt /tmp/requirements.txt

RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r /tmp/requirements.txt

COPY ../app/. /app/


# ---------- Runtime Stage ----------
FROM gcr.io/distroless/python3-debian12

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --from=builder /app /app

# Distroless default UID is 65532 (nonroot)
USER 65532:65532

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 7001

ENTRYPOINT ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7001"]
