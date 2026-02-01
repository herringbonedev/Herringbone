def test_service_imports():
    """
    Boot test:
    Ensures the extractor service imports cleanly.
    Catches missing deps, invalid imports, and Docker-only assumptions.
    """
    import app.main
