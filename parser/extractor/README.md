# 🧠 Herringbone Parser: Extractor Service

The **Extractor Service** is a FastAPI-based microservice that executes parsing rules (cards) stored in the Herringbone framework.  
It takes a log (string or JSON) and applies **regex** and/or **JSONPath** matchers to extract structured values.

---

## 🚀 Overview

The **Extractor Service** is a standalone, pluggable microservice within the Herringbone framework.  
It can operate **independently** or alongside other components like `parser/cardset`, which defines reusable extraction rules (“cards”).  

Each **card** contains:
- A `selector` (the entity or context for extraction)
- A collection of **regex** or **jsonp** rules for parsing logs, text, or structured data.

When integrated, the Extractor automatically consumes cards from `parser/cardset` to standardize parsing logic.  
When deployed on its own, it can directly receive a card and input payload, making it ideal for **modular, on-demand parsing** or embedding in other services.

---

## 🧩 Example Card Schema

```json
{
  "selector": {
    "type": "domain",
    "value": "google.com"
  },
  "regex": [
    { "domain": "([a-z0-9.-]+\.com)" },
    { "url": "https?://[^\s]+" }
  ]
}
```

or for JSONPath-based extraction:

```json
{
  "selector": {
    "type": "source_ip",
    "value": "192.168.1.10"
  },
  "jsonp": [
    { "ip": "$.network.source.ip" }
  ]
}
```

---

## ⚙️ API Endpoints

| Method | Route | Description |
|---------|-------|-------------|
| `POST` | `/parser/extractor/parse` | Parse input using the card’s regex/JSONPath rules |
| `GET` | `/parser/cardset/livez` | Liveness probe (returns `{ "ok": true }`) |
| `GET` | `/parser/cardset/readyz` | Readiness probe (returns `{ "ok": true }`) |

---

## 🧠 Request Body

### Example: Regex Parsing

```json
{
  "card": {
    "selector": {
      "type": "domain",
      "value": "ubuntu.com"
    },
    "regex": [
      { "domain": "([a-z0-9.-]+\.ubuntu\.com)" },
      { "url": "(https?://[^\s]+)" }
    ]
  },
  "input": "Oct 12 14:25:10 webserver01 CRON[3482]: (root) CMD (curl -s https://updates.ubuntu.com/security/index.html)"
}
```

### Example: JSONPath Parsing

```json
{
  "card": {
    "selector": {
      "type": "ip",
      "value": "192.168.1.100"
    },
    "jsonp": [
      { "source_ip": "$.network.source.ip" },
      { "dest_ip": "$.network.dest.ip" }
    ]
  },
  "input": {
    "network": {
      "source": {"ip": "192.168.1.100"},
      "dest": {"ip": "8.8.8.8"}
    }
  }
}
```

---

## 🧾 Example Response

```json
{
  "selector": { "type": "domain", "value": "ubuntu.com" },
  "results": {
    "domain": "updates.ubuntu.com",
    "url": "https://updates.ubuntu.com/security/index.html"
  }
}
```

---

## 🐍 Core Components

### `parser.py`
Defines the **CardParser** class, which supports:
- **Regex mode** → Extracts text from log strings
- **JSONPath mode** → Extracts values from structured JSON

```python
regex_parser = CardParser("regex")
result = regex_parser(card["regex"], input_string)

jsonp_parser = CardParser("jsonp")
result = jsonp_parser(card["jsonp"], json_data)
```

---

### `extractor.py`
Implements the **FastAPI** service with:
- `/parser/extractor/parse` — the main entrypoint
- Pydantic models for `card`, `input`, and response
- Auto-generated `/docs` via OpenAPI

---

## 🧱 Docker

### Build
```bash
docker build -t parser-extractor .
```

### Run
```bash
docker run -d   -p 7003:7003   parser-extractor
```

### Verify
```bash
curl -X POST http://localhost:7003/parser/extractor/parse   -H "Content-Type: application/json"   -d '{"card":{"selector":{"type":"domain","value":"ubuntu.com"},"regex":[{"domain":"([a-z0-9.-]+\.ubuntu\.com)"}]},"input":"curl https://updates.ubuntu.com"}'
```

---

## 🔒 Security

- **Regex isolation:** safely runs compiled regex patterns under `re.IGNORECASE`
- **JSONPath parsing:** powered by `jsonpath-ng==1.7.0` (latest secure version, no known CVEs)
- **Stateless container:** no local data retention
- **Error-safe responses:** all exceptions are sanitized before returning

---

## 🩺 Health Probes

| Route | Purpose |
|--------|----------|
| `/parser/cardset/livez` | Checks if the container is running |
| `/parser/cardset/readyz` | Always returns `{ok: true}` |

---