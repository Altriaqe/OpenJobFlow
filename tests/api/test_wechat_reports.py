from datetime import date
from unittest.mock import Mock

from fastapi.testclient import TestClient

from jobflow.api.analytics import get_connection
from jobflow.api.app import create_app
from jobflow.api.reports import (
    get_wechat_daily_report_sender,
    get_wechat_daily_status_reader,
)


def wechat_client(monkeypatch, *, sender=None, reader=None, connection=None):
    monkeypatch.setenv("REPORT_TRIGGER_TOKEN", "test-trigger-token")
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection or Mock()
    if sender is not None:
        app.dependency_overrides[get_wechat_daily_report_sender] = lambda: sender
    if reader is not None:
        app.dependency_overrides[get_wechat_daily_status_reader] = lambda: reader
    return TestClient(app), app


def test_wechat_send_requires_token_before_service(monkeypatch):
    sender = Mock()
    client, app = wechat_client(monkeypatch, sender=sender)
    try:
        response = client.post("/reports/daily/multi/wechat/send?snapshot_date=2026-08-27")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    sender.assert_not_called()


def test_wechat_send_forwards_snapshot_date(monkeypatch):
    sender = Mock(return_value={"status": "disabled", "snapshot_date": "2026-08-27"})
    connection = Mock()
    client, app = wechat_client(monkeypatch, sender=sender, connection=connection)
    try:
        response = client.post(
            "/reports/daily/multi/wechat/send?snapshot_date=2026-08-27",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    sender.assert_called_once_with(connection, snapshot_date=date(2026, 8, 27))


def test_wechat_status_is_forwarded_without_secrets(monkeypatch):
    reader = Mock(
        return_value={
            "snapshot_date": "2026-08-27",
            "enabled": True,
            "status": "uncertain",
            "manual_action_required": True,
        }
    )
    client, app = wechat_client(monkeypatch, reader=reader)
    try:
        response = client.get(
            "/reports/daily/multi/wechat/status?snapshot_date=2026-08-27",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    serialized = str(response.json()).lower()
    assert response.status_code == 200
    assert "openid" not in serialized
    assert "secret" not in serialized
    assert "message_id" not in serialized


def test_wechat_resend_requires_and_forwards_confirmation(monkeypatch):
    sender = Mock(return_value={"status": "sent", "message_id": 123})
    connection = Mock()
    client, app = wechat_client(monkeypatch, sender=sender, connection=connection)
    try:
        rejected = client.post(
            "/reports/daily/multi/wechat/resend?snapshot_date=2026-08-27",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
        accepted = client.post(
            "/reports/daily/multi/wechat/resend?snapshot_date=2026-08-27&confirm_not_received=true",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert rejected.status_code == 409
    assert accepted.status_code == 200
    sender.assert_called_once_with(
        connection, snapshot_date=date(2026, 8, 27), allow_uncertain=True
    )
