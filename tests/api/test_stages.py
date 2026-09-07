from unittest.mock import Mock

from fastapi.testclient import TestClient

from jobflow.api.app import create_app
from jobflow.api.dependencies import get_connection


def test_stage_status_returns_all_configured_stages():
    connection = Mock()
    connection.cursor.return_value.fetchall.return_value = [
        ("postgres", "succeeded", "数据库可用", None),
        ("ready", "succeeded", "API 就绪", None),
    ]
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    try:
        response = TestClient(app).get("/operations/stages")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    stages = response.json()
    assert len(stages) == 8
    assert stages[0]["id"] == "data_source"
    assert stages[0]["name"] == "数据源"
    assert {"id", "name", "goal", "acceptance", "state"} <= stages[0].keys()
    assert stages[3]["state"] == "已验收"
    assert stages[4]["state"] == "已验收"


def test_stage_status_hides_database_details():
    connection = Mock()
    connection.cursor.return_value.execute.side_effect = RuntimeError("database secret")
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    try:
        response = TestClient(app).get("/operations/stages")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "stage status unavailable"}
    assert "secret" not in response.text
