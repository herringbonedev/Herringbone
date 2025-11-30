# Microservice Port Mappings

This table documents the internal and external port assignments for all Herringbone microservices.  
Internal ports represent the port each container listens on, while external ports (if present) represent the port exposed to the host or load balancer.

| Unit           | Element    | Internal Port | External Port |
|----------------|------------|---------------|----------------|
| detectionengine | matcher    | 7003          | 7003           |
| detectionengine | ruleset    | 7002          | 7002           |
| detectionengine | detector   | None          | None           |
| herringbone     | apps       | 7002          | 7002           |
| herringbone     | logs       | 7002          | 7002           |
| logingestion    | enrichment | None          | None           |
| logingestion    | receiver   | 7002          | 7002           |
| mind            | recon      | 8002          | 8002           |
| mind            | overwatch  | 8002          | 8002           |
| parser          | cardset    | 7002          | 7002           |
| parser          | extractor  | 7002          | 7002           |
