from database import MongoDatabaseHandler
import requests
import time, os

while True:

    try:
        # Load all the rules
        print("[Detector] Loading rules.")
        rules_mongo = MongoDatabaseHandler(collection=os.environ.get("RULES_COLLECTION_NAME"))
        rules = rules_mongo.get_rules()
        
        # Pull out most recent non-detected object
        print("[Detector] Trying to find undetected logs.")

        logs_mongo = MongoDatabaseHandler(collection=os.environ.get("LOGS_COLLECTION_NAME"))
        latest_not_detected = logs_mongo.get_latest_not_detected()
        
        if not latest_not_detected:
            raise("No logs found to run detection.")
        
        else:
            # Send the log over with the rules to overwatch for analysis
            response = requests.post(os.environ.get("OVERWATCH_HOST"), data=latest_not_detected)
            print(response.content)

    except Exception as e:
        print(e)
    
    time.sleep(5)