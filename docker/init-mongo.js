db = db.getSiblingDB("herringbone")

db.scopes.createIndex({ scope: 1 }, { unique: true })

const defaultOrg = db.organizations.findOneAndUpdate(
  { slug: "default" },
  {
    $set: {
      name: "Default",
      slug: "default",
      status: "active",
      updated_at: new Date()
    },
    $setOnInsert: {
      created_at: new Date()
    }
  },
  {
    upsert: true,
    returnDocument: "after"
  }
)

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

print("Default org ensured")
print("Scopes seeded or updated")

db.events.createIndex(
  { context_id: 1, _id: -1 },
  { name: "idx_events_context_id_desc" }
)

db.events.createIndex(
  { context_id: 1, ingested_at: -1 },
  { name: "idx_events_context_ingested_at_desc" }
)

db.event_state.createIndex(
  {
    context_id: 1,
    parsed: 1,
    claimed: 1,
    lease_expires_at: 1,
    created_at: 1,
    _id: 1
  },
  { name: "idx_event_state_parser_claim" }
)

db.event_state.createIndex(
  {
    context_id: 1,
    parsed: 1,
    detected: 1,
    detection_claimed: 1,
    detection_lease_expires_at: 1,
    created_at: 1,
    _id: 1
  },
  { name: "idx_event_state_detector_claim" }
)

db.event_state.createIndex(
  { context_id: 1, event_id: 1 },
  { name: "idx_event_state_context_event_id" }
)

db.event_state.createIndex(
  { context_id: 1, parsed: 1, detected: 1 },
  { name: "idx_event_state_context_parsed_detected" }
)

db.parse_cards.createIndex(
  { context_id: 1 },
  { name: "idx_parse_cards_context" }
)

db.parse_cards.createIndex(
  { context_id: 1, "selector.type": 1, "selector.value": 1 },
  { name: "idx_parse_cards_context_selector" }
)

db.parse_results.createIndex(
  { context_id: 1, event_id: 1 },
  { name: "idx_parse_results_context_event_id" }
)

db.rules.createIndex(
  { context_id: 1 },
  { name: "idx_rules_context" }
)

db.detections.createIndex(
  { context_id: 1, event_id: 1, rule_id: 1 },
  { name: "idx_detections_context_event_rule" }
)

db.detections.createIndex(
  { context_id: 1, inserted_at: -1 },
  { name: "idx_detections_context_inserted_at_desc" }
)

db.incidents.createIndex(
  { context_id: 1, created_at: -1 },
  { name: "idx_incidents_context_created_at_desc" }
)

print("Performance indexes ensured")