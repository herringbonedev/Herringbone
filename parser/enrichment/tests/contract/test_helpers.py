def test_selector_matching(enrichment):
    event = {"raw": "hello ssh world", "source": {"address": "1.2.3.4"}}

    assert enrichment.selector_matches({"type": "raw", "value": "ssh"}, event) is True
    assert enrichment.selector_matches({"type": "raw", "value": "missing"}, event) is False
    assert enrichment.selector_matches({"type": "source_address", "value": "1.2.3.4"}, event) is True
    assert enrichment.selector_matches({"type": "source_address", "value": "9.9.9.9"}, event) is False


def test_result_values_are_lists(enrichment):
    assert enrichment.normalize_results({"a": "x", "b": ["y"]}) == {"a": ["x"], "b": ["y"]}


def test_card_labels_are_always_strings(enrichment):
    assert enrichment.safe_card_label({"name": "card-a"}) == "card-a"
    assert isinstance(enrichment.safe_card_label({"name": {"nested": "bad-shape"}}), str)
    assert enrichment.safe_card_label({"selector": {"type": "raw", "value": "hello"}}) == "raw:hello"
