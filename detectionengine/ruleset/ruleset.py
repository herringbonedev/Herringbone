from flask import Flask, request, jsonify
from bson.json_util import dumps
from database import MongoDatabaseHandler

app = Flask(__name__)

EXPECTED_SCHEMA = {
    "name": str,
    "key": str,
    "value": str,
}

def validate_json(data):

    errors = {}
    for key, expected_type in EXPECTED_SCHEMA.items():
        if key not in data:
            errors[key] = "Missing key"
        elif not isinstance(data[key], expected_type):
            errors[key] = f"Expected {expected_type.__name__}, got {type(data[key]).__name__}"
    return errors

@app.route("/detectionengine/ruleset/insert_rule", methods=["POST"])
def insert_rule():

    if not request.is_json:
        return jsonify({"error": "Invalid request, JSON required"}), 400
    
    data = request.get_json()
    errors = validate_json(data)

    if errors:
        return jsonify({"error": "Invalid JSON structure", "details": errors}), 400
    
    print(f"[RULE INSERT] Attempting to insert {data}")

    try:
        print("Connecting to database...")
        mongo = MongoDatabaseHandler()
        mongo.insert_rule(data)
        del mongo
    except Exception as e:
        print(f"Mongo connection failed. {e}")
        del mongo
        return jsonify({"inserted": False}), 500

    return jsonify({"inserted": True}), 200

@app.route("/detectionengine/ruleset/get_rules", methods=["GET"])
def get_rules():

    print(f"[GET RULES] Getting all the rules.")

    try:
        print("Connecting to database...")
        mongo = MongoDatabaseHandler()
        docs = mongo.get_rules()
        del mongo
        return dumps(docs), 200
    except Exception as e:
        del mongo
        return jsonify({"error": str(e)}), 500
    return jsonify({"inserted": True})

#
# Herringbone requires Liveness and Readiness probes for all services.
#
# The routes below contain the logic for livez and readyz
#

@app.route('/detectionengine/ruleset/livez', methods=['GET'])
def liveness_probe():
    """Checks if the API is up and running.
    """

    return 'OK', 200

@app.route('/detectionengine/ruleset/readyz', methods=['GET'])
def readiness_check():
    """Readiness check to see if the service is able to serve data
    from the MongoDB collection Herringbone.
    """

    mongo = MongoDatabaseHandler()
    if mongo.ready:
        return jsonify({"ready": True}), 200
    else:
        return jsonify({"ready": False}), 503

if __name__ == "__main__":

    app.run(host="0.0.0.0", port=7002)