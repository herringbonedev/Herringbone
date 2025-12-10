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
  description: "Detected a login attempt from an unusual IP address",
  rule: {
    regex: "Failed login from ([0-9]{1,3}\\.){3}[0-9]{1,3}",
    key: "raw_log"
  }
})

db.logs.insertOne({
  source: "firewall",
  raw_log: "Failed login from 192.168.1.55 by root",
  detected: false,
  status: "Pending detection",
  inserted_at: new Date()
})
