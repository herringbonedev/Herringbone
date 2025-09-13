from database import MongoDatabaseHandler
import time, os

while True:

    try:
        # Load all the rules
        rules_mongo = MongoDatabaseHandler(os.environ.get("RULES_COLLECTION_NAME"))
        rules = rules_mongo.get_rules()
        
        # Pull out most recent non-detected object
        logs_mongo = MongoDatabaseHandler(os.environ.get("LOGS_COLLECTION_NAME"))
        get_latest_not_detected = logs_mongo.get_latest_not_detected()

    except Exception as e:
        print(e)
    
    time.sleep(5)