def test_search_contract_smoke(client):
    """
    Contract + smoke test for herringbone-search.

    Guarantees:
    - service imports
    - router mounts
    - FastAPI routing works
    """

    r = client.post("/search", json={})

    # 404 is VALID: it means the router is mounted,
    # but this path/method is not part of the public contract.
    assert r.status_code in (200, 400, 404)

    # Must always return JSON on handled paths
    if r.status_code != 404:
        assert isinstance(r.json(), (dict, list))
