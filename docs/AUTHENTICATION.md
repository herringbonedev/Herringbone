# Developing with herringbone-auth

Every API route must utilize an available dependency found in the `auth` module.

```bash
./modules/modules/auth
```

## User dependencies

These dependencies are for routes that are intended to be interacted with solely by a user.

### get_current_user

Simply requires a user to be logged in with a valid token.

### require_role

Ensures the user has the correct role.

Available roles:
```bash
analyst
admin
```

### require_admin

Shorthand way to require the user to have `admin` role

## Service dependencies

Used for strict Service-to-Service authentication.

### require_service_scope

Requires the token making the request to contain specific scope(s).

Available scopes:

| Scope                      | Description                       |
|----------------------------|-----------------------------------|
| logs:ingest                | Ingest raw logs                  |
| logs:read                  | Read logs                        |
| logs:delete                | Delete logs                      |
| parser:cards:read          | Read parse cards                 |
| parser:cards:write         | Create or update parse cards     |
| parser:results:read        | Read parser results              |
| parser:results:write       | Write parser results             |
| extractor:call             | Call extractor service           |
| detections:rules:read      | Read detection rules             |
| detections:rules:write     | Create or update detection rules |
| detections:run             | Execute detection engine         |
| detections:read            | Read detections                  |
| detections:write           | Write detections                 |
| incidents:read             | Read incidents                   |
| incidents:write            | Create or update incidents       |
| incidents:assign           | Assign incidents                 |
| incidents:close            | Close incidents                  |
| incidents:orchestrate      | Run orchestrations               |
| incidents:correlate        | Run orchestrations               |
| search:query               | Execute search queries           |
| search:saved:read          | Read saved searches              |
| search:saved:write         | Create or update saved searches  |

## Mixed user and service dependencies

In the event a route will be used by both users and services you can use the mix part of the module.

### service_or_user

Allows a service with specific scope(s) or any user with a valid token.

### service_or_role

Allows a service with specific scope(s) or a user with a valid token and a specific role.