from detectionengine.matcher.app.matchengine import MatchEngine


def test_missing_key_falls_back_to_raw():
    engine = MatchEngine()
    result = engine(
        {"regex": "sudo", "key": "nope.path"},
        {"raw": "sudo command executed"},
    )
    assert result["is_matched"] is True
