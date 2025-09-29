FROM registry.access.redhat.com/ubi8/python-311:1-56.1712880527

LABEL Project="Herringbone"
LABEL Version="Beta 1.0.0"
LABEL Tool="Enrichment"

# saner python defaults in containers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

USER root

# Workdir at project root (inside container)
WORKDIR /app

# Copy only requirements first (better layer caching)
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the build context: enrichment code + copied modules/
COPY . .

# Run the enrichment worker (imports use PYTHONPATH=/app, so modules/ is visible)
CMD ["python3", "enrichment.py"]
