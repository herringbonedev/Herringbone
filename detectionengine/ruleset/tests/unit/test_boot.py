# tests/unit/test_boot.py

def test_service_imports():
    """
    Boot test:
    Ensures the service imports cleanly.
    Catches missing deps, syntax errors, circular imports.
    """
    import app.main
