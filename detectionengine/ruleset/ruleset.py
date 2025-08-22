from flask import Flask, request, jsonify
from bson.json_util import dumps
from database import MongoDatabaseHandler


app = Flask(__name__)

@app.route("/detectionengine/ruleset/insert_rule", methods=["GET"])
def insert_rule():

    rule = request.args.get('rule')
    print(f"[RULE INSERT] Attempting to insert {rule}")

    try:
        print("Connecting to database...")
        mongo = MongoDatabaseHandler()
        mongo.insert_rule({"rule":rule})
        del mongo
    except Exception as e:
        print(f"Mongo connection failed. {e}")
        del mongo
        return jsonify({"inserted": False})

    return jsonify({"inserted": True})

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