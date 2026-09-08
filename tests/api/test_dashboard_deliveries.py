from unittest.mock import Mock

from fastapi.testclient import TestClient

from jobflow.api.app import create_app
from jobflow.api.dependencies import get_connection


def test_dashboard_deliveries_reads_telegram_snapshot_status():
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.fetchall.side_effect = [
        [],
        [("telegram", "completed", 2, "2026-09-08T09:13:00+00:00")],
    ]
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    try:
        response = TestClient(app).get("/dashboard/deliveries?snapshot_date=2026-09-08")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {
            "channel": "telegram",
            "status": "sent",
            "attempts": 2,
            "updated_at": "2026-09-08T09:13:00+00:00",
        }
    ]
