from flask import Flask, jsonify, request
from bson.json_util import dumps
from database import MongoDatabaseHandler

app = Flask(__name__)

@app.route("/herringbone/logs/get_docs", methods=["GET"])
def get_docs():

    mongo_handler = MongoDatabaseHandler()

    try:
        n = int(request.args.get('n', 10))  # Default to 10 if not provided
        docs = mongo_handler.get_latest_documents(n)
        del mongo_handler
        return dumps(docs), 200
    except ValueError:
        del mongo_handler
        return jsonify({"error": "Parameter 'n' must be an integer"}), 400
    except Exception as e:
        del mongo_handler
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9002)