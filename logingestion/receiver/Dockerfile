FROM registry.access.redhat.com/ubi8/python-311:1-56.1712880527

# Make Python a bit saner in containers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/herringbone

USER root

# We’ll stage the app under /herringbone so that PYTHONPATH points to the package root
WORKDIR /herringbone

# Copy just the requirements first to leverage Docker layer caching
COPY logingestion/receiver/requirements.txt ./receiver/requirements.txt
RUN pip install --no-cache-dir -r ./receiver/requirements.txt

# Copy only what the receiver needs (receiver + shared modules)
COPY logingestion/receiver ./receiver
COPY modules ./modules

# Expose both protocols on 7002
EXPOSE 7002/udp
EXPOSE 7002/tcp

# Run as a module so imports are package-safe (and PYTHONPATH already set)
CMD ["python3", "-m", "receiver.receiver"]
