import forwarder

def test_forward_data_success(monkeypatch):
    class FakeResp:
        content = b"ok"

    monkeypatch.setattr(
        forwarder.requests,
        "post",
        lambda *a, **kw: FakeResp(),
    )

    ok = forwarder.forward_data("http://example", {"a": 1}, "1.1.1.1")
    assert ok is True


def test_forward_data_failure(monkeypatch):
    monkeypatch.setattr(
        forwarder.requests,
        "post",
        lambda *a, **kw: (_ for _ in ()).throw(Exception("boom")),
    )

    ok = forwarder.forward_data("http://example", {"a": 1}, "1.1.1.1")
    assert ok is False
