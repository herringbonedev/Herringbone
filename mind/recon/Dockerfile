FROM ollama/ollama:latest

RUN apt-get update && \
    apt-get install -y python3 python3-pip curl

EXPOSE 8002/tcp

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt || true

RUN ollama pull gemma:2b

RUN ollama create securitylog -f Modelfile

CMD ["sh", "-c", "ollama serve & sleep 10 && python3 recon.py"]