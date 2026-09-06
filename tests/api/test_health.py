from unittest.mock import Mock

from fastapi.testclient import TestClient

from jobflow.api.app import create_app
from jobflow.api.dependencies import get_connection


def test_health_does_not_open_database():
    app = create_app()
    connection_dependency = Mock(side_effect=AssertionError("database should not be used"))
    app.dependency_overrides[get_connection] = connection_dependency
    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    connection_dependency.assert_not_called()


def test_local_frontend_is_allowed_to_read_health():
    response = TestClient(create_app()).get(
        "/health", headers={"Origin": "http://localhost:5173"}
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unknown_frontend_is_not_allowed_to_read_health():
    response = TestClient(create_app()).get(
        "/health", headers={"Origin": "http://evil.example"}
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_ready_executes_database_probe():
    connection = Mock()
    connection.cursor.return_value.fetchone.return_value = (1,)
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    try:
        response = TestClient(app).get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    connection.cursor.return_value.execute.assert_called_once_with("SELECT 1")


def test_ready_hides_database_error_details():
    connection = Mock()
    connection.cursor.return_value.execute.side_effect = RuntimeError("database secret")
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    try:
        response = TestClient(app).get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "secret" not in response.text


def test_ready_maps_connection_creation_error(monkeypatch):
    monkeypatch.setattr(
        "jobflow.api.dependencies.connect_postgres",
        Mock(side_effect=RuntimeError("database secret")),
    )

    response = TestClient(create_app()).get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "secret" not in response.text
