db = db.getSiblingDB("herringbone");

db.scopes.createIndex({ scope: 1 }, { unique: true });

export const defaultScopes = [

  // Logs
  { scope: "logs:ingest",  description: "Ingest raw logs into the platform", tier: "free" },
  { scope: "logs:read",    description: "Read ingested logs",                tier: "free" },
  { scope: "logs:delete",  description: "Delete logs",                       tier: "free" },

  // Parser
  { scope: "parser:cards:read",    description: "View parser cards",                 tier: "free" },
  { scope: "parser:cards:write",   description: "Create or modify parser cards",     tier: "free" },
  { scope: "parser:results:read",  description: "Read parser results",               tier: "free" },
  { scope: "parser:results:write", description: "Write parser results",              tier: "free" },

  // Extractor
  { scope: "extractor:call", description: "Call the extractor service", tier: "free" },

  // Detection Engine
  { scope: "detections:rules:read",  description: "View detection rules",            tier: "free" },
  { scope: "detections:rules:write", description: "Create or modify detection rules", tier: "free" },
  { scope: "detections:run",         description: "Execute the detection engine",    tier: "free" },
  { scope: "detections:read",        description: "Read generated detections",       tier: "free" },
  { scope: "detections:write",       description: "Write detection results",         tier: "free" },

  // Incidents
  { scope: "incidents:read",        description: "View incidents",             tier: "free" },
  { scope: "incidents:write",       description: "Create or update incidents", tier: "free" },
  { scope: "incidents:assign",      description: "Assign incidents to users",  tier: "free" },
  { scope: "incidents:close",       description: "Close incidents",            tier: "free" },
  { scope: "incidents:orchestrate", description: "Run incident orchestrations", tier: "free" },
  { scope: "incidents:correlate",   description: "Run correlation analysis",   tier: "free" },

  // Search
  { scope: "search:query",       description: "Execute search queries",        tier: "free" },
  { scope: "search:saved:read",  description: "View saved searches",           tier: "free" },
  { scope: "search:saved:write", description: "Create or update saved searches", tier: "free" },

  // Dashboards
  { scope: "dashboard:read", description: "View dashboards", tier: "free" },

  // Platform Roles
  { scope: "platform:admin",   description: "Full platform administration", tier: "free" },
  { scope: "platform:analyst", description: "Platform analyst permissions", tier: "free" },

  // Organization Roles
  { scope: "org:admin",   description: "Organization administrator", tier: "enterprise" },
  { scope: "org:analyst", description: "Organization analyst",       tier: "enterprise" },

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
