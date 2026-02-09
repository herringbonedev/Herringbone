from bson import ObjectId
from routers.logs import encode


def test_encode_objectid():
    oid = ObjectId()
    data = {"_id": oid}
    encoded = encode(data)
    assert encoded["_id"] == str(oid)
