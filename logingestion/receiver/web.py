from flask import Flask, request
from database import MongoDatabaseHandler


app = Flask(__name__)

try:
    print("Connecting to database...")
    mongo = MongoDatabaseHandler()
except Exception as e:
    print(f"Mongo connection failed. {e}")

@app.route('/receiver')
def receiver():
    data = request.args.get('data')
    if data:
        if request.headers.getlist("X-Forwarded-For"):
            addr = request.headers.getlist("X-Forwarded-For")[0].split(',')[0]
        else:
            addr = request.remote_addr
        print(f"[Source Address: {addr}] {data}")

        try:
            mongo.insert_log({"source_address": addr, "raw_log": data})
        except Exception as e:
            print(f"Mongo insert operation failed. {e}")

        return "Data received", 200
    else:
        return "No data received", 400
    
def start_http_receiver():
    print("Receiver type set to HTTP...")
    print("Started on container port 7002")
    app.run("0.0.0.0", 7002)
    