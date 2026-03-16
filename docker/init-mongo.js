db = db.getSiblingDB("herringbone")

db.scopes.createIndex({ scope: 1 }, { unique: true })

const defaultScopes = [

  {
    scope: "logs:ingest",
    category: "logs",
    action: "ingest",
    description: "Ingest raw logs into the platform",
    tier: "free",
    ui_group: "Log Management",
    order: 1
  },
  {
    scope: "logs:read",
    category: "logs",
    action: "read",
    description: "Read ingested logs",
    tier: "free",
    ui_group: "Log Management",
    order: 2
  },
  {
    scope: "logs:delete",
    category: "logs",
    action: "delete",
    description: "Delete logs",
    tier: "free",
    ui_group: "Log Management",
    order: 3
  },

  {
    scope: "parser:cards:read",
    category: "parser",
    action: "read",
    description: "View parser cards",
    tier: "free",
    ui_group: "Parser",
    order: 1
  },
  {
    scope: "parser:cards:write",
    category: "parser",
    action: "write",
    description: "Create or modify parser cards",
    tier: "free",
    ui_group: "Parser",
    order: 2
  },

  {
    scope: "parser:results:read",
    category: "parser",
    action: "read",
    description: "Read parser results",
    tier: "free",
    ui_group: "Parser",
    order: 3
  },

  {
    scope: "parser:results:write",
    category: "parser",
    action: "write",
    description: "Write parser results",
    tier: "free",
    ui_group: "Parser",
    order: 4
  },

  {
    scope: "extractor:call",
    category: "extractor",
    action: "call",
    description: "Call the extractor service",
    tier: "free",
    ui_group: "Extractor",
    order: 1
  },

  {
    scope: "detections:rules:read",
    category: "detections",
    action: "read",
    description: "View detection rules",
    tier: "free",
    ui_group: "Detection Engine",
    order: 1
  },
  {
    scope: "detections:rules:write",
    category: "detections",
    action: "write",
    description: "Create or modify detection rules",
    tier: "free",
    ui_group: "Detection Engine",
    order: 2
  },
  {
    scope: "detections:run",
    category: "detections",
    action: "run",
    description: "Execute the detection engine",
    tier: "free",
    ui_group: "Detection Engine",
    order: 3
  },
  {
    scope: "detections:read",
    category: "detections",
    action: "read",
    description: "Read generated detections",
    tier: "free",
    ui_group: "Detection Engine",
    order: 4
  },
  {
    scope: "detections:write",
    category: "detections",
    action: "write",
    description: "Write detection results",
    tier: "free",
    ui_group: "Detection Engine",
    order: 5
  },

  {
    scope: "incidents:read",
    category: "incidents",
    action: "read",
    description: "View incidents",
    tier: "free",
    ui_group: "Incidents",
    order: 1
  },
  {
    scope: "incidents:write",
    category: "incidents",
    action: "write",
    description: "Create or update incidents",
    tier: "free",
    ui_group: "Incidents",
    order: 2
  },
  {
    scope: "incidents:assign",
    category: "incidents",
    action: "assign",
    description: "Assign incidents",
    tier: "free",
    ui_group: "Incidents",
    order: 3
  },
  {
    scope: "incidents:close",
    category: "incidents",
    action: "close",
    description: "Close incidents",
    tier: "free",
    ui_group: "Incidents",
    order: 4
  },

  {
    scope: "search:query",
    category: "search",
    action: "query",
    description: "Execute search queries",
    tier: "free",
    ui_group: "Search",
    order: 1
  },

  {
    scope: "dashboard:read",
    category: "dashboard",
    action: "read",
    description: "View dashboards",
    tier: "free",
    ui_group: "Dashboards",
    order: 1
  },

  {
    scope: "platform:admin",
    category: "platform",
    action: "admin",
    description: "Full platform administration",
    tier: "free",
    ui_group: "Platform",
    order: 1
  },
  {
    scope: "platform:analyst",
    category: "platform",
    action: "analyst",
    description: "Platform analyst permissions",
    tier: "free",
    ui_group: "Platform",
    order: 2
  },

  {
    scope: "org:admin",
    category: "org",
    action: "admin",
    description: "Organization administrator",
    tier: "enterprise",
    ui_group: "Organization",
    order: 1
  },
  {
    scope: "org:analyst",
    category: "org",
    action: "analyst",
    description: "Organization analyst",
    tier: "enterprise",
    ui_group: "Organization",
    order: 2
  }

]

defaultScopes.forEach(scope => {

  db.scopes.updateOne(
    { scope: scope.scope },
    {
      $set: {
        category: scope.category,
        action: scope.action,
        description: scope.description,
        tier: scope.tier,
        ui_group: scope.ui_group,
        order: scope.order
      },
      $setOnInsert: {
        created_at: new Date()
      }
    },
    { upsert: true }
  )

})

print("Scopes seeded or updated")