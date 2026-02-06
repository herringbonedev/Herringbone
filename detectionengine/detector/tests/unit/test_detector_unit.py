def test_analyze_log_with_rules_no_match(requests_mock):
    requests_mock.post(
        "http://matcher.local/find_match",
        json={"matched": False, "details": "no match"},
        status_code=200,
    )

    from analyzer import analyze_log_with_rules

    rules = [{
        "name": "r1",
        "severity": 10,
        "description": "desc",
        "rule": {"regex": "abc", "key": "raw"},
        "correlate_on": [],
    }]

    out = analyze_log_with_rules({"raw": "hello world"}, rules)
    assert out["detection"] is False
    assert isinstance(out["details"], list)
