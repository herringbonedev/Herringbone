from flask import Flask, request, jsonify
import requests
import json
import os

print(os.popen("ls -la /root/.ollama/models/").read())

app = Flask(__name__)

OLLAMA_URL = 'http://localhost:11434/api/generate'

def prompt_template(raw_logs):
    """Generate prompt template for recon from prompt.text
    """
    return open("app/prompt.text", "r").read() + "here is the list of logs for you to analyze: "+ raw_logs

@app.route('/recon', methods=['POST'])
def recon():
    data = request.get_json()
    raw_logs = data.get('record', '')
    print(f"[*] Recon request received for log: {raw_logs}")

    response = requests.post(OLLAMA_URL, json={
        "model": os.environ.get("OLLAMA_MODEL", "llama3.2:3b"),
        "prompt": prompt_template(raw_logs),
        "stream": False,
        "format": "json"
    })

    print(f"[*] Response from model: {response.text}")

    return response.json().get('response', 'No response from model')

@app.route('/readyz', methods=['GET'])
def readyz():

    response = requests.post(OLLAMA_URL, json={
        "model": "llama3.2:3b",
        "prompt": "Send back just the word 'ready' if the model is ready to process requests",
        "stream": False
    })

    return response.json().get('response', 'No response from model')

@app.route('/livez', methods=['GET'])
def livez():
    return jsonify({"status": "alive"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001)
