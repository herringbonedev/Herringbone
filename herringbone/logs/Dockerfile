FROM python:3.11-slim

WORKDIR /app

# Copy files
COPY requirements.text .
RUN pip install --no-cache-dir -r requirements.text

COPY . .

# Flask listens on 9002
EXPOSE 9002

CMD ["python", "app.py"]