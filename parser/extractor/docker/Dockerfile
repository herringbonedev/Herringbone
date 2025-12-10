# ---------- Builder Stage ----------
FROM python:3.11-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY ../requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r /tmp/requirements.txt

# Copy ONLY the contents of the app/ folder into /app
COPY ../app/. /app/

# ---------- Runtime Stage ----------
FROM python:3.11-slim
WORKDIR /app

COPY --from=builder /install /usr/local
COPY --from=builder /app /app

RUN useradd -u 65532 -m appuser
USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 7006

ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7006"]
