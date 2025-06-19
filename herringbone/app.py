from flask import Flask, render_template
from pymongo import MongoClient
import os

app = Flask(__name__)

# Get env vars
MONGO_HOST = os.environ.get('MONGO_HOST', None)
DB_NAME = os.environ.get("DB_NAME")
COLLECTION_NAME = os.environ.get('COLLECTION_NAME')
MONGO_USER = os.environ.get('MONGO_USER')
MONGO_PASS = os.environ.get('MONGO_PASS')
AUTH_URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}/{DB_NAME}"
client = MongoClient(AUTH_URI)
collection = client[DB_NAME][COLLECTION_NAME]

@app.route("/")
def index():
    documents = list(collection.find())
    return render_template("index.html", documents=documents)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7002)
