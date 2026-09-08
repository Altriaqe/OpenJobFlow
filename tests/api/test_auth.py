from fastapi.testclient import TestClient

from jobflow.api.app import create_app


def test_admin_session_login_and_logout(monkeypatch):
    monkeypatch.setenv("JOBFLOW_ADMIN_TOKEN", "admin-token")
    client = TestClient(create_app())

    assert client.get("/auth/session").status_code == 401
    login = client.post("/auth/login", json={"token": "admin-token"})
    assert login.status_code == 200
    assert client.get("/auth/session").json() == {"status": "authenticated"}
    assert client.post("/auth/logout").json() == {"status": "signed_out"}
    assert client.get("/auth/session").status_code == 401
