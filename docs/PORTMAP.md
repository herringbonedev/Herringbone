# Microservice Port Mappings

This table documents the internal and external port assignments for all
Herringbone microservices.\
Internal ports represent the port each container listens on.\
External ports represent the port exposed to the host or gateway.

Note: As of alpha-0.2.0, HTTP APIs are no longer exposed directly.\
All HTTP traffic flows through the herringbone-proxy service on port
8080.

  Unit              Element        Internal Port    External Port
  ----------------- -------------- ---------------- ----------------
  gateway           proxy          80               8080
  detectionengine   matcher        7003             None
  detectionengine   ruleset        7002             None
  detectionengine   detector       None             None
  herringbone       logs           7010             None
  herringbone       search         7014             None
  herringbone       auth           7001             None
  logingestion      receiver       7004 (TCP/UDP)   7004 (TCP/UDP)
  parser            cardset        7005             None
  parser            extractor      7006             None
  parser            enrichment     None             None
  incidents         correlator     7012             None
  incidents         incidentset    7011             None
  incidents         orchestrator   7013             None
  database          mongodb        27017            27017