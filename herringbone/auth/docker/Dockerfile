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
FROM cgr.dev/chainguard/python:3.11

WORKDIR /app

# Copy Python deps + app
COPY --from=builder /install /usr/local
COPY --from=builder /app /app

# Ensure runtime user is non-root (Chainguard default = 65532)
USER 65532:65532

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 7001

# No shell, direct exec only
ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7001"]
