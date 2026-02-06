def test_analysis_contract_shape(requests_mock):
    requests_mock.post(
        "http://matcher.local/find_match",
        json={"matched": True, "details": "ok"},
        status_code=200,
    )

    from analyzer import analyze_log_with_rules

    rules = [{
        "name": "r1",
        "severity": 10,
        "description": "d",
        "rule": {"regex": "x"},
        "correlate_on": [],
    }]

    out = analyze_log_with_rules({"raw": "x"}, rules)

    assert set(out.keys()) == {"detection", "details"}
    assert isinstance(out["details"], list)
