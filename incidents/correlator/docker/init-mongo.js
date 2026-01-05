db = db.getSiblingDB("herringbone")

db.createUser({
  user: "hbadmin",
  pwd: "hbdevpw123",
  roles: [
    { role: "readWrite", db: "herringbone" },
    { role: "dbAdmin", db: "herringbone" }
  ]
})

db.rules.insertOne({
  _id: "suspicious-login",
  name: "Suspicious Login Attempt",
  severity: 75,
  category: "authentication",
  description: "Detected a failed login from an IP address",
  rule: {
    regex: "Failed login from ([0-9]{1,3}\\.){3}[0-9]{1,3}",
    key: "raw"
  }
})

function minutesAgo(m) {
  return new Date(Date.now() - m * 60 * 1000)
}

const priorities = ["low", "medium", "high", "critical"]
const statuses = ["open", "investigating", "resolved"]

const TOTAL = 50

for (let i = 0; i < TOTAL; i++) {
  const recent = i < 20
  const minutes = recent
    ? Math.floor(Math.random() * 20)
    : Math.floor(Math.random() * 300)

  const when = minutesAgo(minutes)
  const eventId = ObjectId()
  const ip = `192.168.1.${50 + (i % 20)}`

  db.events.insertOne({
    _id: eventId,
    source: {
      kind: "firewall",
      address: "192.168.1.1"
    },
    raw: `Failed login from ${ip} by root`,
    ingested_at: when
  })

  db.parse_results.insertOne({
    event_id: eventId,
    results: {
      user: ["root"],
      ip: [ip],
      auth_success: [false],
      host: ["fw-01"]
    },
    parsed_at: when
  })

  db.detections.insertOne({
    _id: ObjectId(),
    rule_id: "suspicious-login",
    severity: 75,
    entities: {
      user: "root",
      ip: ip,
      host: "fw-01"
    },
    event_ids: [eventId],
    created_at: when
  })
}

const activeIncidentId = ObjectId()

db.incidents.insertOne({
  _id: activeIncidentId,
  title: "Suspicious login activity (active)",
  rule_id: "suspicious-login",
  status: "open",
  priority: "high",
  severity: 75,
  entities: {
    user: "root",
    host: "fw-01"
  },
  detections: [],
  events: [],
  owner: null,
  created_at: minutesAgo(15),
  last_updated: minutesAgo(5)
})

db.incidents.insertOne({
  title: "Old suspicious login activity",
  rule_id: "suspicious-login",
  status: "open",
  priority: "medium",
  severity: 75,
  entities: {
    user: "root",
    host: "fw-01"
  },
  detections: [],
  events: [],
  owner: null,
  created_at: minutesAgo(180),
  last_updated: minutesAgo(180)
})

db.incidents.insertOne({
  title: "Resolved login incident",
  rule_id: "suspicious-login",
  status: "resolved",
  priority: "low",
  severity: 75,
  entities: {
    user: "root",
    host: "fw-01"
  },
  detections: [],
  events: [],
  owner: "analyst1",
  created_at: minutesAgo(60),
  last_updated: minutesAgo(60)
})
