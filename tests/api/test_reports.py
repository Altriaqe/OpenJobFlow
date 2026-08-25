from datetime import date
from unittest.mock import Mock

from fastapi.testclient import TestClient

from jobflow.api.analytics import get_connection
from jobflow.api.app import create_app
from jobflow.api.reports import (
    get_daily_report_sender,
    get_daily_status_reader,
    get_multi_daily_report_sender,
    get_multi_daily_photo_recoverer,
    get_multi_daily_status_reader,
    get_report_sender,
)


def report_client(monkeypatch, sender, connection_provider=None):
    monkeypatch.setenv("REPORT_TRIGGER_TOKEN", "test-trigger-token")
    app = create_app()
    app.dependency_overrides[get_connection] = connection_provider or (lambda: Mock())
    app.dependency_overrides[get_report_sender] = lambda: sender
    return TestClient(app), app


def test_report_endpoint_rejects_missing_token_before_service(monkeypatch):
    sender = Mock()
    connection_provider = Mock()
    client, app = report_client(monkeypatch, sender, connection_provider)
    try:
        response = client.post("/reports/cities/send")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    connection_provider.assert_not_called()
    sender.assert_not_called()


def test_report_endpoint_rejects_wrong_token_before_service(monkeypatch):
    sender = Mock()
    connection_provider = Mock()
    client, app = report_client(monkeypatch, sender, connection_provider)
    try:
        response = client.post(
            "/reports/cities/send",
            headers={"Authorization": "Bearer wrong-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    connection_provider.assert_not_called()
    sender.assert_not_called()


def test_report_endpoint_sends_with_correct_token(monkeypatch):
    sender = Mock(return_value={"status": "sent", "city_count": 2})
    client, app = report_client(monkeypatch, sender)
    try:
        response = client.post(
            "/reports/cities/send",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "sent", "city_count": 2}
    sender.assert_called_once()


def test_report_endpoint_defaults_to_query_mode(monkeypatch):
    sender = Mock(return_value={"status": "sent", "city_count": 1})
    connection = Mock()
    client, app = report_client(monkeypatch, sender, lambda: connection)
    try:
        response = client.post(
            "/reports/cities/send",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    sender.assert_called_once_with(connection, mode="query")


def test_report_endpoint_accepts_ai_mode(monkeypatch):
    sender = Mock(return_value={"status": "sent", "city_count": 1})
    connection = Mock()
    client, app = report_client(monkeypatch, sender, lambda: connection)
    try:
        response = client.post(
            "/reports/cities/send?mode=ai",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    sender.assert_called_once_with(connection, mode="ai")


def test_report_endpoint_rejects_unknown_mode(monkeypatch):
    sender = Mock()
    client, app = report_client(monkeypatch, sender)
    try:
        response = client.post(
            "/reports/cities/send?mode=unknown",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    sender.assert_not_called()


def test_report_endpoint_maps_telegram_failure_to_502(monkeypatch):
    from jobflow.channels.telegram import TelegramDeliveryError

    sender = Mock(side_effect=TelegramDeliveryError("Telegram request failed"))
    client, app = report_client(monkeypatch, sender)
    try:
        response = client.post(
            "/reports/cities/send",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "report delivery failed"}


def test_report_endpoint_maps_telegram_configuration_failure_to_503(monkeypatch):
    from jobflow.channels.telegram import TelegramConfigurationError

    sender = Mock(side_effect=TelegramConfigurationError("missing TELEGRAM_BOT_TOKEN"))
    client, app = report_client(monkeypatch, sender)
    try:
        response = client.post(
            "/reports/cities/send",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "report service unavailable"}


def test_report_endpoint_maps_openai_failure_to_503(monkeypatch):
    from jobflow.ai.openai_summary import OpenAISummaryError

    sender = Mock(side_effect=OpenAISummaryError("OpenAI request failed"))
    client, app = report_client(monkeypatch, sender)
    try:
        response = client.post(
            "/reports/cities/send",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "report service unavailable"}


def daily_report_client(monkeypatch, sender, *, status_reader=None, connection_provider=None):
    monkeypatch.setenv("REPORT_TRIGGER_TOKEN", "test-trigger-token")
    app = create_app()
    app.dependency_overrides[get_connection] = connection_provider or (lambda: Mock())
    app.dependency_overrides[get_daily_report_sender] = lambda: sender
    if status_reader is not None:
        app.dependency_overrides[get_daily_status_reader] = lambda: status_reader
    return TestClient(app), app


def multi_daily_client(monkeypatch, sender, *, status_reader=None, connection_provider=None):
    monkeypatch.setenv("REPORT_TRIGGER_TOKEN", "test-trigger-token")
    app = create_app()
    app.dependency_overrides[get_connection] = connection_provider or (lambda: Mock())
    app.dependency_overrides[get_multi_daily_report_sender] = lambda: sender
    if status_reader is not None:
        app.dependency_overrides[get_multi_daily_status_reader] = lambda: status_reader
    return TestClient(app), app


def multi_recovery_client(monkeypatch, recoverer, *, connection_provider=None):
    monkeypatch.setenv("REPORT_TRIGGER_TOKEN", "test-trigger-token")
    app = create_app()
    app.dependency_overrides[get_connection] = connection_provider or (lambda: Mock())
    app.dependency_overrides[get_multi_daily_photo_recoverer] = lambda: recoverer
    return TestClient(app), app


def test_daily_send_endpoint_forwards_date_and_keyword(monkeypatch) -> None:
    sender = Mock(return_value={"status": "sent", "snapshot_id": 17})
    connection = Mock()
    client, app = daily_report_client(monkeypatch, sender, connection_provider=lambda: connection)
    try:
        response = client.post(
            "/reports/daily/send?snapshot_date=2026-08-18&keyword=AI%20Agent",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    sender.assert_called_once_with(
        connection,
        snapshot_date=date(2026, 8, 18),
        keyword="AI Agent",
    )


def test_daily_endpoint_rejects_missing_token_before_db_access(monkeypatch) -> None:
    sender = Mock()
    connection_provider = Mock()
    client, app = daily_report_client(monkeypatch, sender, connection_provider=connection_provider)
    try:
        response = client.post("/reports/daily/send?snapshot_date=2026-08-18")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    connection_provider.assert_not_called()
    sender.assert_not_called()


def test_daily_send_maps_missing_snapshot_and_delivery_failure(monkeypatch) -> None:
    from jobflow.channels.telegram import TelegramDeliveryError
    from jobflow.reports.daily_service import DailySnapshotNotFound

    for exception, expected_status in [
        (DailySnapshotNotFound("missing"), 404),
        (TelegramDeliveryError("failed"), 502),
    ]:
        client, app = daily_report_client(monkeypatch, Mock(side_effect=exception))
        try:
            response = client.post(
                "/reports/daily/send?snapshot_date=2026-08-18",
                headers={"Authorization": "Bearer test-trigger-token"},
            )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == expected_status


def test_daily_status_exposes_only_operational_metadata(monkeypatch) -> None:
    status_reader = Mock(
        return_value={
            "snapshot_id": 17,
            "snapshot_date": "2026-08-18",
            "keyword": "AI Agent",
            "status": "completed",
            "text_sent": True,
            "photo_sent": True,
        }
    )
    client, app = daily_report_client(monkeypatch, Mock(), status_reader=status_reader)
    try:
        response = client.get(
            "/reports/daily/status?snapshot_date=2026-08-18",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    serialized = str(body).lower()
    assert response.status_code == 200
    assert body["status"] == "completed"
    assert "token" not in serialized
    assert "chat_id" not in serialized
    assert "proxy" not in serialized
    assert "message_text" not in serialized


def test_multi_daily_send_forwards_date(monkeypatch) -> None:
    sender = Mock(return_value={"status": "sent", "snapshot_ids": [11, 12, 13, 14]})
    connection = Mock()
    client, app = multi_daily_client(
        monkeypatch,
        sender,
        connection_provider=lambda: connection,
    )
    try:
        response = client.post(
            "/reports/daily/multi/send?snapshot_date=2026-08-20",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    sender.assert_called_once_with(connection, snapshot_date=date(2026, 8, 20))


def test_multi_daily_status_does_not_expose_secrets(monkeypatch) -> None:
    reader = Mock(
        return_value={
            "status": "missing_snapshots",
            "snapshot_date": "2026-08-20",
            "present_keywords": ["AI Agent"],
            "missing_keywords": ["Python开发", "Java开发", "数据分析"],
        }
    )
    client, app = multi_daily_client(monkeypatch, Mock(), status_reader=reader)
    try:
        response = client.get(
            "/reports/daily/multi/status?snapshot_date=2026-08-20",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    serialized = str(response.json()).lower()
    assert response.status_code == 200
    assert "token" not in serialized
    assert "chat_id" not in serialized
    assert "proxy" not in serialized


def test_multi_daily_endpoint_rejects_missing_token_before_db_access(monkeypatch) -> None:
    sender = Mock()
    connection_provider = Mock()
    client, app = multi_daily_client(
        monkeypatch,
        sender,
        connection_provider=connection_provider,
    )
    try:
        response = client.post("/reports/daily/multi/send?snapshot_date=2026-08-20")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    connection_provider.assert_not_called()
    sender.assert_not_called()


def test_multi_daily_send_maps_incomplete_snapshots_to_409(monkeypatch) -> None:
    from jobflow.reports.multi_keyword_service import MultiKeywordSnapshotMissing

    sender = Mock(side_effect=MultiKeywordSnapshotMissing(("数据分析",)))
    client, app = multi_daily_client(monkeypatch, sender)
    try:
        response = client.post(
            "/reports/daily/multi/send?snapshot_date=2026-08-20",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {"detail": "daily snapshots incomplete"}
    assert "数据分析" not in str(response.json())


def test_multi_daily_send_maps_manual_state_to_409(monkeypatch) -> None:
    from jobflow.reports.multi_keyword_service import MultiKeywordDeliveryStateError

    sender = Mock(side_effect=MultiKeywordDeliveryStateError("secret state"))
    client, app = multi_daily_client(monkeypatch, sender)
    try:
        response = client.post(
            "/reports/daily/multi/send?snapshot_date=2026-08-22",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {"detail": "report delivery requires manual action"}
    assert "secret state" not in str(response.json())


def test_multi_photo_recovery_rejects_missing_token_before_db_access(monkeypatch) -> None:
    recoverer = Mock()
    connection_provider = Mock()
    client, app = multi_recovery_client(
        monkeypatch,
        recoverer,
        connection_provider=connection_provider,
    )
    try:
        response = client.post(
            "/reports/daily/multi/recover-photo"
            "?snapshot_date=2026-08-22&confirm_text_visible=true"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    connection_provider.assert_not_called()
    recoverer.assert_not_called()


def test_multi_photo_recovery_requires_explicit_confirmation(monkeypatch) -> None:
    recoverer = Mock()
    client, app = multi_recovery_client(monkeypatch, recoverer)
    try:
        response = client.post(
            "/reports/daily/multi/recover-photo?snapshot_date=2026-08-22",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {"detail": "visible text confirmation required"}
    recoverer.assert_not_called()


def test_multi_photo_recovery_forwards_explicit_confirmation(monkeypatch) -> None:
    recoverer = Mock(return_value={"status": "sent", "photo_message_id": 202})
    connection = Mock()
    client, app = multi_recovery_client(
        monkeypatch,
        recoverer,
        connection_provider=lambda: connection,
    )
    try:
        response = client.post(
            "/reports/daily/multi/recover-photo"
            "?snapshot_date=2026-08-22&confirm_text_visible=true",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "sent", "photo_message_id": 202}
    recoverer.assert_called_once_with(
        connection,
        snapshot_date=date(2026, 8, 22),
        confirm_text_visible=True,
    )


def test_multi_photo_recovery_maps_uncertain_delivery_to_502(monkeypatch) -> None:
    from jobflow.channels.telegram import TelegramDeliveryUncertain

    recoverer = Mock(side_effect=TelegramDeliveryUncertain("secret", attempts=1))
    client, app = multi_recovery_client(monkeypatch, recoverer)
    try:
        response = client.post(
            "/reports/daily/multi/recover-photo"
            "?snapshot_date=2026-08-22&confirm_text_visible=true",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "report delivery failed"}
    assert "secret" not in str(response.json())
