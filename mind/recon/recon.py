from flask import Flask, request, jsonify
import requests
import json
import os

print(os.popen("tree /root/.ollama/models/").read())

app = Flask(__name__)

OLLAMA_URL = 'http://localhost:11434/api/generate'

def prompt_template(raw_log):
    """Generate prompt template for recon from prompt.text
    """
    return open("prompt.text", "r").read() + "input: "+ raw_log

@app.route('/recon', methods=['POST'])
def recon():
    data = request.get_json()
    raw_log = data.get('record', '')
    print(f"[*] Recon request received for log: {raw_log}")

    response = requests.post(OLLAMA_URL, json={
        "model": "herringbone-mind-recon",
        "prompt": prompt_template(raw_log),
        "stream": False
    })

    return response.json().get('response', 'No response from model')

@app.route('/ready', methods=['GET'])
def ready():

    response = requests.post(OLLAMA_URL, json={
        "model": "herringbone-mind-recon",
        "prompt": "Send back just the word 'ready' if the model is ready to process requests.",
        "stream": False
    })

    return response.json().get('response', 'No response from model')

@app.route('/healthz', methods=['GET'])
def healthz():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002)
