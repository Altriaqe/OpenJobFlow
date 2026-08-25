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
