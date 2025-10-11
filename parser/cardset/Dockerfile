# ---------- Build stage ----------
FROM cgr.dev/chainguard/python:latest-dev AS builder
WORKDIR /app
USER root

# Create a venv and install deps
ENV VENV_PATH=/app/.venv
COPY requirements.txt .
RUN python -m venv "$VENV_PATH" \
 && "$VENV_PATH/bin/pip" install --no-cache-dir -r requirements.txt

# Copy all app code (includes modules/, cardset.py, etc.)
COPY . .
# Ensure nonroot can read at runtime
RUN chown -R 65532:65532 /app

# ---------- Runtime stage ----------
FROM cgr.dev/chainguard/python:latest
WORKDIR /app
# Bring in the built app + venv
COPY --from=builder /app /app

# Non-root user (Chainguard's default UID)
USER 65532
EXPOSE 7002

# Make the venv first on PATH and ensure imports work
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Start FastAPI via uvicorn, bind to all interfaces
ENTRYPOINT ["python","-m","uvicorn"]
CMD ["cardset:app","--host","0.0.0.0","--port","7002"]
