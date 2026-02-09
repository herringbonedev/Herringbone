from bson import ObjectId
from routers.logs import merge_parse_results


class MongoStub:
    def find(self, collection, filter_query):
        return [
            {
                "event_id": filter_query["event_id"]["$in"][0],
                "results": {"ip": ["1.1.1.1"], "user": ["alice"]},
            }
        ]


def test_merge_parse_results():
    oid = ObjectId()
    mongo = MongoStub()
    parsed = merge_parse_results(mongo, [oid])

    assert parsed[oid]["ip"] == ["1.1.1.1"]
    assert parsed[oid]["user"] == ["alice"]
