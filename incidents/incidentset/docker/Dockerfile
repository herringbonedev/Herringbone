# ---------- Builder Stage ----------
FROM python:3.11-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

# copy requirements
COPY incidents/incidentset/requirements.txt /tmp/requirements.txt

# copy shared package source
COPY modules /modules

# install deps + shared modules
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --target=/python-packages -r /tmp/requirements.txt

# copy app
COPY incidents/incidentset/app /app

# ---------- Runtime Stage ----------
FROM gcr.io/distroless/python3-debian12
WORKDIR /app

COPY --from=builder /app /app
COPY --from=builder /python-packages /python-packages

USER 65532:65532

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/python-packages

EXPOSE 7011

ENTRYPOINT ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7011"]
