def test_analyze_log_with_rules_multiple_rules(requests_mock):
    requests_mock.post(
        "http://matcher.local/find_match",
        json={"matched": True, "details": "ok"},
        status_code=200,
    )

    from analyzer import analyze_log_with_rules

    rules = [
        {
            "name": "r1",
            "severity": 42,
            "description": "desc1",
            "rule": {"regex": "hello", "key": "raw"},
            "correlate_on": [],
        },
        {
            "name": "r2",
            "severity": 90,
            "description": "desc2",
            "rule": {"regex": "world", "key": "raw"},
            "correlate_on": [],
        },
    ]

    out = analyze_log_with_rules({"raw": "hello world"}, rules)

    assert out["detection"] is True
    assert len(out["details"]) == 2
