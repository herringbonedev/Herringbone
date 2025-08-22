from flask import Flask, request
from database import MongoDatabaseHandler


app = Flask(__name__)

@app.route("/insert_rule", methods=["GET"])
def insert_rule():

    rule = request.args.get('rule')
    print(f"[RULE INSERT] Attempting to insert {rule}")

    try:
        print("Connecting to database...")
        mongo = MongoDatabaseHandler()
        mongo.insert_log({"rule":rule})
    except Exception as e:
        print(f"Mongo connection failed. {e}")

