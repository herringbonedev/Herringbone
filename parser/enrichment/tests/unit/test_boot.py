def test_service_imports():
    """
    Boot test:
    Ensures the enrichment service imports cleanly.
    Catches missing deps, invalid imports, and Docker-only assumptions.
    """
    import app.enrichment
