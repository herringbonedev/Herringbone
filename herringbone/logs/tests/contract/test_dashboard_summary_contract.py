def test_dashboard_summary_contract(client):
    r = client.get("/herringbone/logs/dashboard/summary")
    body = r.json()

    for k in ["events_24h", "detected", "undetected", "high_severity", "failed"]:
        assert k in body
        assert isinstance(body[k], int)
