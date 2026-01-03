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

db.event_status.insertOne({
  event_id: eventId,
  parsed: true,
  detected: false
})
