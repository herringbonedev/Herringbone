from database import MongoDatabaseHandler
import requests
import time, os
import json
import traceback

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
        for rule in rules:
            if "_id" in rule:
                del rule["_id"]
        
        # Pull out most recent non-detected object
        print("[Detector] Trying to find undetected logs.")

        logs_mongo = MongoDatabaseHandler(collection=os.environ.get("LOGS_COLLECTION_NAME"))
        latest_not_detected = logs_mongo.get_latest_not_detected()
        log_id = latest_not_detected.get("_id") if latest_not_detected else None
        latest_not_detected.pop("_id", None)
        latest_not_detected.pop("last_update", None)
        latest_not_detected.pop("last_processed", None)
        
        if not latest_not_detected or not log_id:
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
            
            # Mark all logs as detected for now
            print(f"Storing results: {str(analysis)}")
            logs_mongo.update_detection_status(log_id, analysis)
            

    except Exception as e:
        print(e)
        print(traceback.format_exc())
    
    time.sleep(5)