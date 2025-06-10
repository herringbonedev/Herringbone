from pymongo import MongoClient
from datetime import datetime
import os
import json

class MongoNotSet(Exception):
    """If the MONGO_HOST is not set in the container environment variables"""
    pass

class MongoDatabaseHandler:

    def __init__(self):
        self.MONGO_HOST = os.environ.get('MONGO_HOST', None)
        self.DB_NAME = os.environ.get("DB_NAME")
        self.COLLECTION_NAME = os.environ.get('COLLECTION_NAME')
        self.MONGO_USER = os.environ.get('MONGO_USER')
        self.MONGO_PASS = os.environ.get('MONGO_PASS')

        uri_parts = self.MONGO_HOST.split("://")
        if len(uri_parts) != 2:
            raise Exception("Invalid MONGO_HOST format. Expecting mongodb://hostname:port")
        
        self.AUTH_URI = f"{uri_parts[0]}://{self.MONGO_USER}:{self.MONGO_PASS}@{uri_parts[1]}"

        if self.MONGO_HOST is not None:
            self.client = MongoClient(self.MONGO_HOST)
            self.db = self.client[self.DB_NAME]
            self.collection = self.db[self.COLLECTION_NAME]

        else:
            raise MongoNotSet("MONGO_HOST is not set in the container environment variables.")
        
        try:
            self.client = MongoClient(self.AUTH_URI)
            self.db = self.client[self.DB_NAME]
            self.collection = self.db[self.COLLECTION_NAME]

        except Exception as e:
            raise Exception(f"Failed to connect to MongoDB: {e}")
        
    def insert_log(self, log_object):
        try:
            result = self.collection.insert_one(log_object)
            print(f"[✓] Inserted log with _id: {result.inserted_id}")
        except Exception as e:
            print(f"[✗] Error inserting log: {e}")

    def close(self):
        self.client.close()