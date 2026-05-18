from bson import ObjectId
from routers.logs import merge_parse_results


class MongoStub:
    def find_with_context(self, collection, filter_query, context_id):
        return [
            {
                "event_id": filter_query["event_id"]["$in"][0],
                "context_id": context_id,
                "results": {"ip": ["1.1.1.1"], "user": ["alice"]},
            }
        ]


def test_merge_parse_results():
    oid = ObjectId()
    mongo = MongoStub()
    parsed = merge_parse_results(mongo, [str(oid)], "default")

    assert parsed[str(oid)]["ip"] == ["1.1.1.1"]
    assert parsed[str(oid)]["user"] == ["alice"]
