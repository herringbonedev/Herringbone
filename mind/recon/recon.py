from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

OLLAMA_URL = 'http://localhost:11434/api/generate'

PROMPT_TEMPLATE = """
You are a cybersecurity threat analysis AI trained to extract structured intelligence from raw logs. Given a log message, respond with only a JSON object using STIX 2.1-compatible fields, MITRE ATT&CK mappings, and typed indicators of compromise.

Return only the following fields when available:

- "log_type": High-level source category (e.g., "Windows Event Log", "Linux Syslog", "Apache Access Log")
- "operating_system": The specific OS (e.g., "Windows 10", "Ubuntu 22.04")
- "origin": Country of origin based on source IP or hostname, if determinable
- "description": Short summary of the log event
- "malicious": Score from 0 (benign) to 10 (highly malicious)
- "event_type": Classification like "authentication", "network", "file_access", "execution", "registry_change", etc.
- "attack_tactic": Mapped MITRE ATT&CK tactic (e.g., "Execution", "Persistence")
- "attack_technique": MITRE ATT&CK technique name and ID (e.g., "Command and Scripting Interpreter (T1059)")
- "ioc": Object grouping the extracted indicators of compromise, broken down by type:
  - "IPv4Address": List of IP addresses
  - "domain": List of FQDNs or domains
  - "url": List of URLs
  - "username": List of usernames or account names
  - "filepath": List of local file paths
  - "process": List of process names or commands
  - "registry_key": List of registry keys accessed or modified
  - "hash": List of file hashes (MD5, SHA1, SHA256)

- "confidence": Integer from 0–100 representing the model’s certainty in its output

Respond with a valid JSON object only — no additional explanations, comments, or null fields.

input log: {record}
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
