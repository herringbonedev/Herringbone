db = db.getSiblingDB("herringbone");

db.scopes.createIndex({ scope: 1 }, { unique: true });

const defaultScopes = [

  // Log ingestion
  { scope: "logs:ingest", description: "Ingest raw logs", tier: "free" },
  { scope: "logs:read", description: "Read logs", tier: "free" },
  { scope: "logs:delete", description: "Delete logs", tier: "enterprise" },

  // Parser
  { scope: "parser:cards:read", description: "Read parse cards", tier: "free" },
  { scope: "parser:cards:write", description: "Create or update parse cards", tier: "free" },
  { scope: "parser:results:read", description: "Read parser results", tier: "free" },
  { scope: "parser:results:write", description: "Write parser results", tier: "free" },

  // Extractor
  { scope: "extractor:call", description: "Call extractor service", tier: "free" },

  // Detection engine
  { scope: "detections:rules:read", description: "Read detection rules", tier: "free" },
  { scope: "detections:rules:write", description: "Create or update detection rules", tier: "free" },
  { scope: "detections:run", description: "Execute detection engine", tier: "free" },
  { scope: "detections:read", description: "Read detections", tier: "free" },
  { scope: "detections:write", description: "Write detections", tier: "free" },

  // Incidents
  { scope: "incidents:read", description: "Read incidents", tier: "free" },
  { scope: "incidents:write", description: "Create or update incidents", tier: "free" },
  { scope: "incidents:assign", description: "Assign incidents", tier: "free" },
  { scope: "incidents:close", description: "Close incidents", tier: "free" },
  { scope: "incidents:orchestrate", description: "Run orchestrations", tier: "free" },
  { scope: "incidents:correlate", description: "Run orchestrations", tier: "free" },

  // Search
  { scope: "search:query", description: "Execute search queries", tier: "free" },
  { scope: "search:saved:read", description: "Read saved searches", tier: "free" },
  { scope: "search:saved:write", description: "Create or update saved searches", tier: "enterprise" },

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
