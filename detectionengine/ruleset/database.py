from pymongo import MongoClient
from datetime import datetime
import os
import json
import codecs

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
        self.AUTH_URI = f"mongodb://{self.MONGO_USER}:{self.MONGO_PASS}@{self.MONGO_HOST}/{self.DB_NAME}"

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

    def clean_codec(self,data):
        """Clean the codec data by decoding it from unicode escape sequences.
        """

        decoded = data.encode('utf-8').decode('unicode_escape')
        decoded = codecs.decode(decoded.encode('utf-8'), 'unicode_escape')
        return decoded.strip()

    def insert_log(self, log_object):
        
        try:
            result = self.collection.insert_one(log_object)
            print(f"[✓] Inserted rule with _id: {result.inserted_id}")
        except Exception as e:
            print(f"[✗] Error inserting rule: {e}")

    def close(self):
        self.client.close()