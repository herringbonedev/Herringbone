from pymongo import MongoClient, ReturnDocument
from datetime import datetime
from bson.objectid import ObjectId

import os
import json
import codecs

class MongoNotSet(Exception):
    """If the MONGO_HOST is not set in the container environment variables.
    """

    pass

class MongoDatabaseHandler:
    
    def __init__(self, collection):
        self.MONGO_HOST = os.environ.get('MONGO_HOST', None)
        self.DB_NAME = os.environ.get("DB_NAME")
        self.COLLECTION_NAME = collection
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

    def clean_codec(self,data):
        """Clean the codec data by decoding it from unicode escape sequences.
        """

        decoded = data.encode('utf-8').decode('unicode_escape')
        decoded = codecs.decode(decoded.encode('utf-8'), 'unicode_escape')
        return decoded.strip()

    def insert_detection(self, log_object):
        
        try:
            result = self.collection.insert_one(log_object)
            print(f"[✓] Inserted rule with _id: {result.inserted_id}")
        except Exception as e:
            raise Exception(f"[✗] Error inserting rule: {e}")

    def get_rules(self):
        """Retrieve n most recent documents sorted by _id descending.
        """

        try:
            documents = self.collection.find().sort("_id", -1).limit(1000)
            return list(documents)
        except Exception as e:
            raise Exception(f"Failed to retrieve latest documents: {e}")
        
    def get_latest_not_detected(self):
        """Retrieve the latest document that has not been marked detected.
        """
        
        return self.collection.find_one({"detected": False, "recon": True})
    
    def update_detection_status(self, log_id, analysis):
        """Update and return the updated log document.
        """
        
        oid = log_id if isinstance(log_id, ObjectId) else ObjectId(str(log_id))
        doc = self.collection.find_one_and_update(
            {"_id": oid},
            {"$set": {
                "detected": True,
                "detection": bool(analysis.get("match")),
                "detection_reason": analysis.get("reason"),
                "updated_at": datetime.utcnow(),
            }},
            return_document=ReturnDocument.AFTER
        )
        if doc is None:
            print(f"[!] No document matched _id={oid}")
        else:
            print(f"[✓] Updated log {_id if (_id:=doc.get('_id')) else oid} detected={doc.get('detection')}")

    def close(self):
        self.client.close()