import os
import pytest
from urllib.parse import urlparse
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from testcontainers.mongodb import MongoDbContainer


@pytest.fixture(scope="session")
def mongo_container():
    container = MongoDbContainer("mongo:7")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def integration_mongo_env(mongo_container):
    url = mongo_container.get_connection_url()
    parsed = urlparse(url)

    host = f"{parsed.hostname}:{parsed.port}"
    db_name = "herringbone"
    hb_user = "herringbone_test"
    hb_pass = "herringbone_test"

    # If container has auth, create db-scoped user
    if parsed.username and parsed.password:
        admin_uri = f"mongodb://{parsed.username}:{parsed.password}@{host}/admin"
        client = MongoClient(admin_uri, serverSelectionTimeoutMS=5000)
        try:
            client.admin.command("ping")
            db = client[db_name]
            try:
                db.command(
                    "createUser",
                    hb_user,
                    pwd=hb_pass,
                    roles=[{"role": "readWrite", "db": db_name}],
                )
            except OperationFailure as e:
                if getattr(e, "code", None) != 51003:
                    raise
        finally:
            client.close()

        os.environ["MONGO_USER"] = hb_user
        os.environ["MONGO_PASS"] = hb_pass
    else:
        os.environ["MONGO_USER"] = ""
        os.environ["MONGO_PASS"] = ""
    
    os.environ["EXTRACTOR_MODE"] = "local"
    os.environ["MONGO_HOST"] = host
    os.environ["DB_NAME"] = db_name

    yield
