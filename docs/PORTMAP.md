# Microservice Port Mappings

This table documents the internal and external port assignments for all Herringbone microservices.  
Internal ports represent the port each container listens on, while external ports (if present) represent the port exposed to the host or load balancer.

| Unit           | Element    | Internal Port | External Port |
|----------------|------------|---------------|----------------|
| detectionengine | matcher    | 7003          | 7003           |
| detectionengine | ruleset    | 7002          | 7002           |
| detectionengine | detector   | 7002          | null           |
| herringbone     | apps       | 7002          | null           |
| herringbone     | logs       | 7002          | null           |
| logingestion    | enrichment | 7002          | null           |
| logingestion    | receiver   | 7002          | null           |
| mind            | recon      | 8002          | null           |
| mind            | overwatch  | 8002          | null           |
| parser          | cardset    | 7002          | null           |
| parser          | extractor  | 7002          | null           |
