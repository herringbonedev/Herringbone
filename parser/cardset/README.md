# 🧩 CardSet Microservice

The **CardSet Service** is a modular FastAPI-based microservice within the **Herringbone** framework.  
It manages **“cards”** — structured parsing rules used by Herringbone’s AI enrichment pipeline to extract data patterns (regex or JSONPath) based on a given selector (like `domain`, `source_ip`, etc.).

---

## 🚀 Features

- **Insert, Pull, Update, Delete** card definitions via REST API  
- **MongoDB-backed persistence layer** using `HerringboneMongoDatabase`  
- **Schema validation** through `CardSchema`  
- **Kubernetes-ready** with `/livez` and `/readyz` probes  
- **Stateless container**, ideal for scaling in microservice environments  

---

## 🧱 API Endpoints

| Method | Route | Description |
|---------|-------|-------------|
| `POST` | `/parser/cardset/insert_card` | Insert a new valid card into MongoDB |
| `POST` | `/parser/cardset/pull_cards` | Query cards by selector type/value |
| `POST` | `/parser/cardset/update_card` | Update an existing card |
| `POST` | `/parser/cardset/delete_cards` | Delete cards matching a selector |
| `GET` | `/parser/cardset/livez` | Liveness probe |
| `GET` | `/parser/cardset/readyz` | Readiness probe (verifies Mongo connection) |

---

## 🧩 Card Structure

Example valid card JSON:

```json
{
  "selector": {
    "type": "domain",
    "value": "google.com"
  },
  "regex": [
    { "domain": "(?:[a-z0-9-]+\.)*google\.com" },
    { "url": "https?:\/\/[^\s]+" }
  ]
}
```

Alternate format using JSONPath extractors:

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

## ⚙️ Environment Variables

| Variable | Description | Default |
|-----------|-------------|----------|
| `MONGO_HOST` | MongoDB hostname | `127.0.0.1` |
| `MONGO_PORT` | MongoDB port | `27017` |
| `MONGO_USER` | MongoDB username | `hbadmin` |
| `MONGO_PASS` | MongoDB password | `hbdevpw123` |
| `DB_NAME` | MongoDB database name | `herringbone` |
| `COLLECTION_NAME` | Target collection for cards | `cards` |

---

## 🐳 Docker Build & Run

### Build
```bash
docker build -t cardset-service .
```

### Run
```bash
docker run -d   -e MONGO_HOST=192.168.1.100   -e MONGO_USER=hbadmin   -e MONGO_PASS=hbdevpw123   -e DB_NAME=herringbone   -e COLLECTION_NAME=cards   -p 7002:7002   cardset-service
```

### Access the API
```bash
curl -X POST http://localhost:7002/parser/cardset/pull_cards   -H "Content-Type: application/json"   -d '{"domain": "google.com"}'
```

---

## 🧠 Health Checks

These are used for Kubernetes or container orchestration:

- `/parser/cardset/livez` → returns `{"ok": true}`
- `/parser/cardset/readyz` → returns `{"ok": true}` only when MongoDB is connected

---

## 🧪 Local Development

Run the service directly using Uvicorn:
```bash
uvicorn cardset:app --host 0.0.0.0 --port 7002 --reload
```

---

## 🧭 Example Responses

**Insert valid card**
```bash
curl -X POST http://localhost:7002/parser/cardset/insert_card   -H "Content-Type: application/json"   -d '{"selector":{"type":"domain","value":"example.com"},"regex":[{"domain":".*example\.com"}]}'
```

Response:
```json
{"ok": true, "message": "Valid card. Inserted into database."}
```

**Pull existing cards**
```bash
curl -X POST http://localhost:7002/parser/cardset/pull_cards   -H "Content-Type: application/json"   -d '{"domain":"example.com"}'
```

Response:
```json
{"ok": true, "count": 1, "cards": [...]}
```