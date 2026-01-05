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

for (let i = 0; i < 20; i++) {
  const recent = i < 10
  const when = recent ? minutesAgo(Math.floor(Math.random() * 20))
                      : minutesAgo(120 + Math.floor(Math.random() * 120))

  const eventId = ObjectId()

  db.events.insertOne({
    _id: eventId,
    source: {
      kind: "firewall",
      address: "192.168.1.1"
    },
    raw: `Failed login from 192.168.1.${50 + i} by root`,
    ingested_at: when
  })

  db.parse_results.insertOne({
    event_id: eventId,
    results: {
      username: ["root"],
      source_ip: [`192.168.1.${50 + i}`],
      auth_success: [false]
    },
    parsed_at: when
  })

  db.detections.insertOne({
    event_id: eventId,
    rule_id: "suspicious-login",
    severity: 75,
    inserted_at: when
  })

  db.incidents.insertOne({
    title: `Suspicious login activity #${i + 1}`,
    rule_id: "suspicious-login",
    status: recent ? "open" : "resolved",
    priority: priorities[Math.floor(Math.random() * priorities.length)],
    detections: [eventId.toString()],
    events: [eventId.toString()],
    owner: null,
    created_at: when,
    last_updated: when
  })
}