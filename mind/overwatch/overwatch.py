from flask import Flask, request, jsonify
import requests
import json
import os

print(os.popen("tree /root/.ollama/models/").read())

app = Flask(__name__)

OLLAMA_URL = 'http://localhost:11434/api/generate'

def prompt_template(raw_log, rules):
    """Generate prompt template for recon from prompt.text
    """
    return open("prompt.text", "r").read() + " here is the log for you to analyze: "+ raw_log +" and here are the rules"+ rules

@app.route('/overwatch', methods=['POST'])
def overwatch():
    data = request.get_json()
    raw_log = data["logs"]
    rules = data["rules"]
    print(f"[*] Overwatch request received for log: {raw_log} \nRules:\n{"-".join(rules)}")

    response = requests.post(OLLAMA_URL, json={
        "model": "llama3.2:3b",
        "prompt": prompt_template(raw_log, rules),
        "stream": False,
        "format": "json"
    })

    print(f"[*] Response from model: {response.text}")

    return response.json().get('response', 'No response from model')

@app.route('/ready', methods=['GET'])
def ready():

    response = requests.post(OLLAMA_URL, json={
        "model": "llama3.2:3b",
        "prompt": "Send back just the word 'ready' if the model is ready to process requests.",
        "stream": False
    })

    return response.json().get('response', 'No response from model')

@app.route('/healthz', methods=['GET'])
def healthz():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002)
