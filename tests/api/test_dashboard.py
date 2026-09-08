from unittest.mock import Mock

from fastapi.testclient import TestClient

from jobflow.api.app import create_app
from jobflow.api.dependencies import get_connection


def test_dashboard_summary_returns_real_sections():
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [(12, 3), (5, "2026-09-07T10:00:00+00:00", "succeeded")]
    cursor.fetchall.side_effect = [
        [],
        [("health", "succeeded", "检查通过", None)],
        [],
    ]
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    try:
        response = TestClient(app).get("/dashboard/summary")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["job_count"] == 12
    assert len(payload["stages"]) == 8
    assert payload["alerts"] == []
