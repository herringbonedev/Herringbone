FROM ollama/ollama:latest

ENV OLLAMA_NUM_PARALLEL=4
ENV OLLAMA_MAX_BATCH_SIZE=16
ENV OLLAMA_KEEP_ALIVE=1

# Install dependencies
RUN apt-get update && apt-get install -y python3 python3-pip curl
RUN apt-get update && apt-get install -y tree

# Set working directory
WORKDIR /app

# Copy app source and model files
COPY ./recon.py /app/recon.py
COPY ./prompt.text /app/prompt.text
COPY ./requirements.txt /app/requirements.txt
COPY ./herringbone-mind-recon /app/herringbone-mind-recon

# Install Python dependencies (if any)
RUN pip install --no-cache-dir -r requirements.txt || true

# Expose necessary ports
EXPOSE 8002
EXPOSE 11434

# Start Ollama, copy model files, and run the app
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["ollama serve & sleep 10 && \
mkdir -p /root/.ollama/models/manifests/registry.ollama.ai/library/herringbone-mind-recon && \
mkdir -p /root/.ollama/models/blobs && \
cp -r /app/herringbone-mind-recon/manifests/registry.ollama.ai/library/herringbone-mind-recon /root/.ollama/models/manifests/registry.ollama.ai/library && \
cp -r /app/herringbone-mind-recon/blobs /root/.ollama/models && \
python3 recon.py"]
