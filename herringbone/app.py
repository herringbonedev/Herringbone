from flask import Flask, render_template
from pymongo import MongoClient
from bson import ObjectId
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

def convert_objectids(doc):
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, dict):
            doc[key] = convert_objectids(value)
    return doc

@app.route("/")
def index():
    documents = [convert_objectids(doc) for doc in collection.find()]
    return render_template("index.html", documents=documents)

@app.route("/healthz")
def healthz():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7002)
