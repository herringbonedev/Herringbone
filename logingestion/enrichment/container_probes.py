#
# Herringbone requires Liveness and Readiness probes for all services.
#
# The routes below contain the logic for livez and readyz
#

from pymongo import MongoClient, ReturnDocument
import os, sys

class MongoNotSet(Exception):
    """If the MONGO_HOST is not set in the container environment variables"""
    pass

MONGO_HOST = os.environ.get('MONGO_HOST', None)
DB_NAME = os.environ.get("DB_NAME", None)
COLLECTION_NAME = os.environ.get('COLLECTION_NAME', None)
MONGO_USER = os.environ.get('MONGO_USER', None)
MONGO_PASS = os.environ.get('MONGO_PASS', None)

def readyz():
    if MONGO_HOST is not None:
        client = MongoClient(MONGO_HOST)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        AUTH_URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}/{DB_NAME}"

        try:
            client = MongoClient(AUTH_URI)
            db = client[DB_NAME]
            collection = db[COLLECTION_NAME]
            return {"readyz": True, "reason": "MongoDB connection success"}

        except Exception as e:
            return {"readyz": False, "reason": "Failed to connect to MongoDB: "+ e}

    else:
        return {"readyz": False, "reason": "MONGO_HOST is not set in the container environment variables."}

def livez():
    return {"livez":True, "reason":""}

if __name__ == "__main__":

    if "readyz" in sys.argv:
        readyz()
    elif "livez" in sys.argv:
        livez()
    else:
        print("No probe specified.")