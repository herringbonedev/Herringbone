FROM ollama/ollama:latest

ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get update && \
    apt-get install -y python3 python3-pip curl

EXPOSE 8001

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["/bin/sh", "-c"]
CMD ["ollama serve & sleep 10 && ollama pull llama3.2:3b && python3 app/recon.py"]
