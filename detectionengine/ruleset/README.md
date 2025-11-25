# RuleSet API

CRUD Operation API for rules that are structured to work with the other Herringbone detection engine services.

## API Endpoints

### Rule Operations

| Method | Path                                   | Description             |
|--------|----------------------------------------|-------------------------|
| POST   | `/detectionengine/ruleset/insert_rule` | Insert a new rule       |
| GET    | `/detectionengine/ruleset/get_rules`   | Retrieve all rules      |
| POST   | `/detectionengine/ruleset/update_rule` | Update an existing rule |
| GET    | `/detectionengine/ruleset/delete_rule` | Delete a rule by `_id`  |

### Health Checks

| Path                                 | Purpose         |
|--------------------------------------|-----------------|
| `/detectionengine/ruleset/livez`     | Liveness probe  |
| `/detectionengine/ruleset/readyz`    | Readiness probe |

## Environment Variables

| Variable          | Description               |
|-------------------|---------------------------|
| `MONGO_USER`      | MongoDB username          |
| `MONGO_PASS`      | MongoDB password          |
| `DB_NAME`         | Database name             |
| `COLLECTION_NAME` | MongoDB collection name   |
| `MONGO_HOST`      | MongoDB host              |
| `AUTH_DB`         | Authentication database   |

## Development Commands

```
make up       # Start containers
make down     # Stop and remove containers/volumes
make rebuild  # Rebuild the image
make logs     # View service logs
make shell    # Shell into the service container
make fmt      # Format with black
make lint     # flake8 lint
```