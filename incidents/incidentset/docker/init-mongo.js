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

// 30 days = 43,200 minutes
const MONTH_MINUTES = 30 * 24 * 60

for (let i = 0; i < 50; i++) {
  // random base time anywhere in last 30 days
  const baseMinutes = Math.floor(Math.random() * MONTH_MINUTES)

  // burst behavior (clusters)
  const burstOffset =
    Math.random() < 0.4
      ? Math.floor(Math.random() * 30)   // burst window
      : Math.floor(Math.random() * 240)  // normal spread

  const when = minutesAgo(baseMinutes + burstOffset)
  const eventId = ObjectId()

  db.events.insertOne({
    _id: eventId,
    source: {
      kind: "firewall",
      address: "192.168.1.1"
    },
    raw: `Failed login from 192.168.1.${50 + (i % 200)} by root`,
    ingested_at: when
  })

  db.parse_results.insertOne({
    event_id: eventId,
    results: {
      username: ["root"],
      source_ip: [`192.168.1.${50 + (i % 200)}`],
      auth_success: [false]
    },
    parsed_at: when
  })

  db.event_state.insertOne({
    event_id: eventId,
    parsed: true,
    detected: true,
    detection: true,
    severity: 75,
    last_stage: "detector",
    last_updated: when,
    analysis: {
      detection: true,
      details: [
        {
          rule_name: "Suspicious Login Attempt",
          severity: 75,
          description: "Detected a failed login from an IP address",
          matched: true
        }
      ]
    }
  })

  db.detections.insertOne({
    event_id: eventId,
    detection: true,
    severity: 75,
    analysis: {
      detection: true
    },
    inserted_at: when
  })

  db.incidents.insertOne({
    title: `Suspicious login activity #${i + 1}`,
    description: "Failed login detected for privileged account",
    status: statuses[Math.floor(Math.random() * statuses.length)],
    priority: priorities[Math.floor(Math.random() * priorities.length)],
    detections: [eventId.toString()],
    events: [eventId.toString()],
    owner: null,
    notes: [
      {
        message: "Incident created from detection",
        created_at: when
      }
    ],
    created_at: when,
    updated_at: when
  })
}
