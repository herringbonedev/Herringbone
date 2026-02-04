# ---------- Builder Stage ----------
FROM python:3.14-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY ../requirements.txt /tmp/requirements.txt

# copy shared package source
COPY ../modules /modules

RUN pip install --upgrade pip setuptools wheel && \
    pip install --prefix=/install --no-cache-dir -r /tmp/requirements.txt

# Copy ONLY the contents of the app/ folder into /app
COPY ../app/. /app/

# ---------- Runtime Stage ----------
FROM python:3.14-slim
WORKDIR /app

COPY --from=builder /install /usr/local
COPY --from=builder /app /app
COPY --from=builder /modules /modules

RUN useradd -u 65532 -m appuser
USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/modules

EXPOSE 7004
EXPOSE 7004/udp

ENTRYPOINT ["python3", "receiver.py"]
