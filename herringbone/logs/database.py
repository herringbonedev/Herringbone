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
        self.ready = False

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
            self.ready = True

        except Exception as e:
            raise Exception(f"Failed to connect to MongoDB: {e}")
    
    def get_latest_documents(self, n):
        """
        Retrieve n most recent documents where:
        recon == True AND detection_results.detected == True
        """
        try:
            query = {
                "recon": True,
                "detection_results.detected": True
            }

            documents = (
                self.collection
                    .find(query)
                    .sort("_id", -1)
                    .limit(n)
            )

            return list(documents)

        except Exception as e:
            raise Exception(f"Failed to retrieve latest documents: {e}")
    
