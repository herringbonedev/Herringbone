db = db.getSiblingDB("herringbone");

db.createUser({
  user: "hbuser",
  pwd: "hbpass",
  roles: [
    { role: "readWrite", db: "herringbone" }
  ]
});
