from flask import Flask, request, jsonify
import requests
import json

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

    response = requests.post(OLLAMA_URL, json={
        "model": "gemma:2b",
        "prompt": prompt_template(raw_log),
        "stream": False
    })

    return response.json().get('response', 'No response from model')

@app.route('/healthz', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002)
