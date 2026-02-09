from routers.auth import is_bootstrap_required


def test_bootstrap_required_when_no_users(fake_mongo):
    assert is_bootstrap_required(fake_mongo) is True
