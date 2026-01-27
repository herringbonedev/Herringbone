# ---------- Builder Stage ----------
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY ../requirements.txt /tmp/requirements.txt

# Install into a clean directory we control
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --target=/python-packages -r /tmp/requirements.txt

COPY ../app/. /app/


# ---------- Runtime Stage ----------
FROM gcr.io/distroless/python3-debian12

WORKDIR /app

# Copy app + packages
COPY --from=builder /app /app
COPY --from=builder /python-packages /python-packages

# Non-root user
USER 65532:65532

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/python-packages

EXPOSE 7001

ENTRYPOINT ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7012"]
