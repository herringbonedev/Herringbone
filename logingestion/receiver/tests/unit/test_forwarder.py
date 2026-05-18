class FakeForwardBatcher:
    def __init__(self):
        self.items = []

    def enqueue(self, data, source_addr, kind="forwarded"):
        self.items.append({"data": data, "source_addr": source_addr, "kind": kind})
        return True

    def enqueue_many(self, events):
        accepted = 0
        dropped = 0
        for event in events:
            if not isinstance(event, dict) or event.get("data") is None:
                dropped += 1
                continue
            accepted += 1
            self.items.append(event)
        return accepted, dropped


def test_forward_data_queues_to_batcher(monkeypatch, forwarder_module):
    fake = FakeForwardBatcher()
    monkeypatch.setattr(forwarder_module, "get_forward_batcher", lambda route: fake)

    assert forwarder_module.forward_data("http://example/logingestion/remote", "hello", "1.1.1.1") is True
    assert fake.items == [{"data": "hello", "source_addr": "1.1.1.1", "kind": "forwarded"}]


def test_forward_many_queues_to_batcher(monkeypatch, forwarder_module):
    fake = FakeForwardBatcher()
    monkeypatch.setattr(forwarder_module, "get_forward_batcher", lambda route: fake)

    accepted, dropped = forwarder_module.forward_many(
        "http://example/logingestion/remote",
        [
            {"data": "one", "source_addr": "1.1.1.1"},
            {"data": "two", "source_addr": "2.2.2.2"},
            {"source_addr": "missing-data"},
        ],
    )

    assert accepted == 2
    assert dropped == 1
    assert len(fake.items) == 2


def test_bulk_route_defaults_to_remote_bulk(forwarder_module):
    assert (
        forwarder_module._bulk_route("http://example/logingestion/remote")
        == "http://example/logingestion/remote/bulk"
    )
