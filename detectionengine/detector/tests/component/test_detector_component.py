def test_analyze_log_with_rules_detection_true(requests_mock):
    requests_mock.post(
        "http://matcher.local/find_match",
        json={"matched": True, "details": "Regex evaluated successfully"},
        status_code=200,
    )

    from analyzer import analyze_log_with_rules

    rules = [{
        "name": "r1",
        "severity": 50,
        "description": "desc",
        "rule": {"regex": "hello", "key": "raw"},
        "correlate_on": ["user"],
    }]

    out = analyze_log_with_rules({"raw": "hello world"}, rules)

    assert out["detection"] is True
    assert len(out["details"]) == 1
    assert out["details"][0]["rule_name"] == "r1"
