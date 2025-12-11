db = db.getSiblingDB("herringbone")

db.createUser({
  user: "hbadmin",
  pwd: "hbdevpw123",
  roles: [
    { role: "readWrite", db: "herringbone" },
    { role: "dbAdmin", db: "herringbone" }
  ]
})

db.logs.insertOne({
  source: "firewall",
  raw_log: "Failed login from 192.168.1.55 by root",
  detected: false,
  status: "Pending detection",
  inserted_at: new Date()
})
