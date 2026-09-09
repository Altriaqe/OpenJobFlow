from unittest.mock import Mock

from fastapi.testclient import TestClient

from jobflow.api.app import create_app
from jobflow.api.dependencies import get_connection


def test_dashboard_workbench_returns_safe_date_snapshot(monkeypatch):
    from jobflow.api import dashboard

    connection = Mock()
    monkeypatch.setattr(
        dashboard,
        "build_delivery_workbench",
        lambda *args, **kwargs: {
            "date": "2026-09-08",
            "date_state": "past",
            "snapshot_available": True,
            "article_available": True,
            "stages": [],
            "channels": [
                {"channel": "telegram", "status": "sent", "actions": []},
                {"channel": "wechat", "status": "not_sent", "actions": ["send"]},
            ],
        },
    )
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    try:
        response = TestClient(app).get("/dashboard/workbench?snapshot_date=2026-09-08")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["channels"][1]["actions"] == ["send"]


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
