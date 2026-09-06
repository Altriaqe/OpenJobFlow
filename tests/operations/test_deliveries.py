from datetime import date

import pytest

from jobflow.operations.deliveries import manual_telegram_delivery
from jobflow.db.operations import claim_delivery_action, finish_delivery_action


def test_manual_delivery_requires_admin_token(monkeypatch):
    monkeypatch.setenv("JOBFLOW_ADMIN_TOKEN", "admin")
    with pytest.raises(PermissionError):
        manual_telegram_delivery(date(2026, 9, 5), "wrong", lambda _: None)


def test_manual_delivery_forwards_explicit_date(monkeypatch):
    monkeypatch.setenv("JOBFLOW_ADMIN_TOKEN", "admin")
    received = []
    result = manual_telegram_delivery(date(2026, 9, 5), "admin", received.append)
    assert received == [date(2026, 9, 5)]
    assert result.status == "sent"


def test_delivery_action_claim_is_idempotent():
    from unittest.mock import Mock

    cursor = Mock()
    cursor.rowcount = 1
    connection = Mock()
    connection.cursor.return_value = cursor
    assert (
        claim_delivery_action(
            connection, report_date=date(2026, 9, 5), channel="telegram", action="manual_delivery"
        )
        is True
    )
    cursor.rowcount = 0
    assert (
        claim_delivery_action(
            connection, report_date=date(2026, 9, 5), channel="telegram", action="manual_delivery"
        )
        is False
    )


def test_delivery_action_can_finish_without_exposing_external_id():
    from unittest.mock import Mock

    cursor = Mock()
    connection = Mock()
    connection.cursor.return_value = cursor
    finish_delivery_action(
        connection,
        report_date=date(2026, 9, 5),
        channel="wechat",
        action="manual_delivery",
        status="created",
        external_id="private-id",
    )
    assert "status = %s" in cursor.execute.call_args.args[0]
