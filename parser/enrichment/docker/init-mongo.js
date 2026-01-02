db = db.getSiblingDB("herringbone")

// Create local dev user
db.createUser({
  user: "hbadmin",
  pwd: "hbdevpw123",
  roles: [
    { role: "readWrite", db: "herringbone" },
    { role: "dbAdmin", db: "herringbone" }
  ]
})

// Collections used by the current pipeline
db.createCollection("events")
db.createCollection("event_state")
db.createCollection("parse_cards")
db.createCollection("event_parses")

// Example parse card
db.parse_cards.insertOne({
  name: "extract_ip_from_auth_failure",
  selector: {
    type: "raw",
    value: "Failed login"
  },
  regex: [
    {
      ip_address: "([0-9]{1,3}\\.){3}[0-9]{1,3}"
    }
  ],
  jsonp: [],
  enabled: true,
  created_at: new Date()
})

// Example event
const eventId = ObjectId()

db.events.insertOne({
  _id: eventId,
  raw: "<34>Jan  1 15:10:41 host sshd: Failed login from 192.168.1.55 for user root",
  source: {
    address: "192.168.1.10",
    kind: "udp"
  },
  event_time: new Date(),
  ingested_at: new Date()
})

// Initial state for the event
db.event_state.insertOne({
  event_id: eventId,
  parsed: false,
  enriched: false,
  detected: false,
  severity: null,
  last_updated: new Date()
})
