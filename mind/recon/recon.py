from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

OLLAMA_URL = 'http://localhost:11434/api/generate'

PROMPT_TEMPLATE = """
You are a log analysis AI. Given a raw log message, respond with only a JSON object containing:

"log_type": the OS or app name,
"origin": country if possible,
"description": a short event summary,
"malicious": a score from 0 (benign) to 10 (very malicious)

Example output:

"log_type": "Windows 10",
"origin": "United States",
"description": "Login event",
"malicious": "10"

Now analyze this log: {record}
"""

@app.route('/recon', methods=['POST'])
def recon():
    data = request.get_json()
    record = data.get('record', '')
    question = "Evaluate my log according to the template given."

    prompt = PROMPT_TEMPLATE.format(record=record)

    response = requests.post(OLLAMA_URL, json={
        "model": "gemma:2b",
        "prompt": prompt,
        "stream": False
    })

    return response.json().get('response', 'No response from model')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002)
