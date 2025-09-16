from database import MongoDatabaseHandler
import requests
import time, os
import json

# Start message
print(f"""[Detector] started with the following parameters.

Overwatch endpoint: {os.environ.get("OVERWATCH_HOST")}
MongoDB Host: {os.environ.get("MONGO_HOST")}
MongoDB Database: {os.environ.get("DB_NAME")}
Rules collection: {os.environ.get("RULES_COLLECTION_NAME")}
Logs collection: {os.environ.get("LOGS_COLLECTION_NAME")}
Detections collection: {os.environ.get("DETECTIONS_COLLECTION_NAME")}
""")

while True:

    try:
        # Load all the rules
        print("[Detector] Loading rules.")
        rules_mongo = MongoDatabaseHandler(collection=os.environ.get("RULES_COLLECTION_NAME"))
        rules = rules_mongo.get_rules()
        del rules["_id"]
        
        # Pull out most recent non-detected object
        print("[Detector] Trying to find undetected logs.")

        logs_mongo = MongoDatabaseHandler(collection=os.environ.get("LOGS_COLLECTION_NAME"))
        latest_not_detected = logs_mongo.get_latest_not_detected()
        log_id = latest_not_detected["_id"]
        del latest_not_detected["_id"]
        del latest_not_detected["last_update"]
        del latest_not_detected["last_processed"]
        
        if not latest_not_detected:
            raise Exception("No logs found to run detection.")
        
        else:
            # Print out the data to be sent to overwatch
            to_analyze = {"log":latest_not_detected, "rules": rules}
            print(to_analyze)

            # Send the log over with the rules to overwatch for analysis
            response = requests.post(os.environ.get("OVERWATCH_HOST"), 
                                     json=to_analyze,
                                     timeout=1000)
            analysis = json.loads(response.content.decode("utf-8"))

            if analysis["match"]:
                logs_mongo.update_detection_status(log_id)

    except Exception as e:
        print(e)
    
    time.sleep(5)