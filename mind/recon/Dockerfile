FROM ollama/ollama:latest

RUN apt-get update && \
    apt-get install -y python3 python3-pip curl

EXPOSE 8002/tcp

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["/bin/sh", "-c"]
CMD ["ollama serve & sleep 10 && ollama pull llama3.2:3b && python3 recon.py"]
