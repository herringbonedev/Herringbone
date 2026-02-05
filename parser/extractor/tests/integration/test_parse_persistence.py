def test_parse_sudo_session_opened(client):
    r = client.post(
        "/parser/extractor/parse",
        json={
            "card": {
                "selector": {
                    "type": "raw",
                    "value": " session opened for user "
                },
                "regex": [
                    {"pam_service": "pam_unix\\(([^)]+)\\)"},
                    {"pam_user": "session\\s+opened\\s+for\\s+user\\s+([a-zA-Z0-9._-]+)"},
                    {"by_user": "\\bby\\s+\\(uid=(\\d+)\\)"},
                ],
            },
            "input": (
                "<86>Feb  4 23:21:16 andrew-ThinkPad-P1-Gen-7 sudo: "
                "pam_unix(sudo:session): session opened for user root(uid=0) by (uid=1000)"
            ),
        },
    )

    assert r.status_code == 200

    body = r.json()
    assert body == {
        "results": {
            "pam_service": "sudo:session",
            "pam_user": "root",
            "by_user": "1000",
        }
    }
