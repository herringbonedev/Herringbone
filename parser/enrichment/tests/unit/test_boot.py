def test_enrichment_imports(enrichment):
    assert hasattr(enrichment, "process_batch")
    assert hasattr(enrichment, "selector_matches")
    assert hasattr(enrichment, "build_success_doc")
