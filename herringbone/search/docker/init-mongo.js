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

const eventId = ObjectId()

db.events.insertOne({
  _id: eventId,
  source: {
    kind: "firewall",
    address: "192.168.1.1"
  },
  raw: "Failed login from 192.168.1.55 by root",
  ingested_at: new Date()
})

db.parse_results.insertOne({
  event_id: eventId,
  results: {
    username: ["root"],
    source_ip: ["192.168.1.55"],
    auth_success: [false]
  },
  parsed_at: new Date()
})

db.event_state.insertOne({
  event_id: eventId,
  parsed: true,
  detected: true,
  detection: true,
  severity: 75,
  last_stage: "detector",
  last_updated: new Date(),
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

const detectionId = ObjectId()

db.detections.insertOne({
  _id: detectionId,
  event_id: eventId,
  detection: true,
  severity: 75,
  analysis: {
    detection: true
  },
  inserted_at: new Date()
})

db.incidents.insertOne({
  title: "Suspicious login activity",
  description: "Failed login detected for privileged account",
  status: "open",
  priority: "high",
  detections: [detectionId.toString()],
  events: [eventId.toString()],
  owner: null,
  notes: [
    {
      message: "Incident created from detection",
      created_at: new Date()
    }
  ],
  created_at: new Date(),
  updated_at: new Date()
})
