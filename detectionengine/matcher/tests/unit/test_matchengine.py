from detectionengine.matcher.app.matchengine import MatchEngine


def test_regex_match_true():
    engine = MatchEngine()
    result = engine(
        {"regex": "hello", "key": "raw"},
        {"raw": "hello world"},
    )
    assert result["is_matched"] is True
