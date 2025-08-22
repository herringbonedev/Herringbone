from flask import Flask, request, jsonify
from database import MongoDatabaseHandler


app = Flask(__name__)

@app.route("/detectionengine/insert_rule", methods=["GET"])
def insert_rule():

    rule = request.args.get('rule')
    print(f"[RULE INSERT] Attempting to insert {rule}")

    try:
        print("Connecting to database...")
        mongo = MongoDatabaseHandler()
        mongo.insert_log({"rule":rule})
    except Exception as e:
        print(f"Mongo connection failed. {e}")
        return jsonify({"inserted": False})

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

if __name__ == "__main__":

    app.run(host="0.0.0.0", port=7002)