docker exec -it herringbone-mongodb-1 sh -lc '
MONGO_ROOT_USER="$(printenv MONGO_INITDB_ROOT_USERNAME)"
MONGO_ROOT_PASS="$(printenv MONGO_INITDB_ROOT_PASSWORD)"

mongosh \
  -u "$MONGO_ROOT_USER" \
  -p "$MONGO_ROOT_PASS" \
  --authenticationDatabase admin \
  /docker-entrypoint-initdb.d/init-mongo.js
'