from app.main import app


def test_delete_rule_requires_admin(client):
    # Clear overrides so real auth is enforced
    app.dependency_overrides.clear()

    res = client.get(
        "/detectionengine/ruleset/delete_rule?id=507f1f77bcf86cd799439011"
    )

    assert res.status_code in (401, 403)
