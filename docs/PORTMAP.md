# Microservice Port Mappings

This table documents the internal and external port assignments for all Herringbone microservices.  
Internal ports represent the port each container listens on, while external ports (if present) represent the port exposed to the host or load balancer.

| Unit           | Element    | Internal Port | External Port |
|----------------|------------|---------------|----------------|
| detectionengine | matcher    | 7003          | 7003           |
| detectionengine | ruleset    | 7002          | 7002           |
| detectionengine | detector   | None          | None           |
| herringbone     | logs       | 7010          | 7010           |
| parser          | enrichment | None          | None           |
| logingestion    | receiver   | 7004          | 7004           |
| mind            | recon      | 8001          | 8001           |
| parser          | cardset    | 7005          | 7005           |
| parser          | extractor  | 7006          | 7006           |
