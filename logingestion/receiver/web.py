from flask import Flask, request

app = Flask(__name__)

@app.route('/receiver')
def receiver():
    data = request.args.get('data')
    if data:
        if request.headers.getlist("X-Forwarded-For"):
            addr = request.headers.getlist("X-Forwarded-For")[0].split(',')[0]
        else:
            addr = request.remote_addr
        print(f"[Source Address: {addr}] {data}")
        return "Data received", 200
    else:
        return "No data received", 400
    
def start_http_receiver():
    print("Receiver type set to HTTP...")
    print("Started on container port 7002")
    app.run("0.0.0.0", 7002)
    