from unittest.mock import Mock

from fastapi.testclient import TestClient

from jobflow.api.app import create_app
from jobflow.api.dependencies import get_connection


def test_operation_checks_returns_recent_checks():
    connection = Mock()
    connection.cursor.return_value.fetchall.return_value = [
        ("health", "succeeded", "检查通过", None),
    ]
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    try:
        response = TestClient(app).get("/operations/checks")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {"name": "health", "status": "succeeded", "summary": "检查通过", "error": None}
    ]


def test_operation_runs_returns_recent_runs():
    connection = Mock()
    connection.cursor.return_value.fetchall.return_value = [
        (1, "server_check", None, "succeeded", None, "2026-09-06T16:20:00", None),
    ]
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    try:
        response = TestClient(app).get("/operations/runs")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["kind"] == "server_check"
