db = db.getSiblingDB("herringbone");

db.scopes.createIndex({ scope: 1 }, { unique: true });

const defaultScopes = [

  // Platform
  { scope: "platform:health", description: "Read platform health status", tier: "free" },
  { scope: "platform:metrics", description: "Read platform metrics", tier: "enterprise" },
  { scope: "platform:config:read", description: "Read platform configuration", tier: "enterprise" },
  { scope: "platform:config:write", description: "Modify platform configuration", tier: "enterprise" },

  // Authentication / IAM
  { scope: "auth:users:read", description: "List users", tier: "free" },
  { scope: "auth:users:write", description: "Create or update users", tier: "enterprise" },
  { scope: "auth:services:read", description: "List service accounts", tier: "enterprise" },
  { scope: "auth:services:write", description: "Create or update service accounts", tier: "enterprise" },
  { scope: "auth:tokens:create", description: "Generate service tokens", tier: "enterprise" },
  { scope: "auth:scopes:read", description: "List available scopes", tier: "free" },
  { scope: "auth:scopes:write", description: "Create or delete scopes", tier: "enterprise" },

  // Log ingestion
  { scope: "logs:ingest", description: "Ingest raw logs", tier: "free" },
  { scope: "logs:read", description: "Read logs", tier: "free" },
  { scope: "logs:delete", description: "Delete logs", tier: "enterprise" },

  // Parser
  { scope: "parser:cards:read", description: "Read parse cards", tier: "free" },
  { scope: "parser:cards:write", description: "Create or update parse cards", tier: "free" },
  { scope: "parser:results:read", description: "Read parser results", tier: "free" },
  { scope: "parser:results:write", description: "Write parser results", tier: "free" },

  // Enrichment / extractor
  { scope: "extractor:call", description: "Call extractor service", tier: "enterprise" },
  { scope: "enrichment:read", description: "Read enrichment results", tier: "enterprise" },
  { scope: "enrichment:write", description: "Write enrichment results", tier: "enterprise" },

  // Detection engine
  { scope: "detections:rules:read", description: "Read detection rules", tier: "free" },
  { scope: "detections:rules:write", description: "Create or update detection rules", tier: "free" },
  { scope: "detections:run", description: "Execute detection engine", tier: "free" },
  { scope: "detections:read", description: "Read detections", tier: "free" },
  { scope: "detections:write", description: "Write detections", tier: "free" },

  // Incidents
  { scope: "incidents:read", description: "Read incidents", tier: "free" },
  { scope: "incidents:write", description: "Create or update incidents", tier: "free" },
  { scope: "incidents:assign", description: "Assign incidents", tier: "enterprise" },
  { scope: "incidents:close", description: "Close incidents", tier: "enterprise" },

  // Search
  { scope: "search:query", description: "Execute search queries", tier: "free" },
  { scope: "search:saved:read", description: "Read saved searches", tier: "free" },
  { scope: "search:saved:write", description: "Create or update saved searches", tier: "enterprise" },

  // Administrative
  { scope: "admin:internal", description: "Internal administrative access", tier: "enterprise" },
];

defaultScopes.forEach(s => {
  const exists = db.scopes.findOne({ scope: s.scope });
  if (!exists) {
    db.scopes.insertOne({
      ...s,
      created_at: new Date(),
    });
  }
});

print("Seeded scopes collection");
