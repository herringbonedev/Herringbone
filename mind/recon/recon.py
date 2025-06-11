from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

OLLAMA_URL = 'http://localhost:11434/api/generate'

PROMPT_TEMPLATE = """
You are a cybersecurity recon analyst. Given the log below, answer this question in a concise and technical manner using the following format:

You must remember. This will be read and processed by another program. Don't use any human communication. Just give the answer.

Don't say things like: Here's my revaluation or anything. Only use the keys I've given.

"log_type":"Your evaluation of what operating system, application or whatever kind of source this log came from",
"origin":"The country of origin that this log came from",
"description":"a description of what this log is",
"malicious":"Your evaluation if it is malicious or not from a scale of 1 (least malicious) to 100 (most malicious)"

Heres the log to evaluate: {record}
"""

@app.route('/recon', methods=['POST'])
def recon():
    data = request.get_json()
    record = data.get('record', '')
    question = "Evaluate my log according to the template given."

    prompt = PROMPT_TEMPLATE.format(record=record)

    response = requests.post(OLLAMA_URL, json={
        "model": "tinyllama",
        "prompt": prompt,
        "stream": False
    })

    return response.json().get("response", "")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002)
