from unittest.mock import Mock

import pytest

from jobflow.ai.openai_summary import OpenAISummaryError
from jobflow.reports import service
from jobflow.reports.service import send_city_report


def connection_with_rows(rows):
    connection = Mock()
    connection.cursor.return_value.fetchall.return_value = rows
    return connection


def test_send_city_report_skips_external_calls_for_empty_data():
    summary_generator = Mock()
    sender = Mock()

    result = send_city_report(
        connection_with_rows([]),
        summary_generator=summary_generator,
        sender=sender,
    )

    assert result == {"status": "skipped", "city_count": 0}
    summary_generator.assert_not_called()
    sender.assert_not_called()


def test_send_city_report_generates_and_sends_report():
    rows = [{"city": "Hangzhou", "job_count": 12}]
    summary_generator = Mock(return_value="城市岗位报告")
    sender = Mock()

    result = send_city_report(
        connection_with_rows([("Hangzhou", 12)]),
        mode="ai",
        summary_generator=summary_generator,
        sender=sender,
    )

    summary_generator.assert_called_once_with(rows)
    sender.assert_called_once_with("城市岗位报告")
    assert result == {"status": "sent", "city_count": 1}


def test_send_city_report_uses_telegram_as_default_sender(monkeypatch):
    query_report = Mock(return_value="固定查询简报")
    telegram_sender = Mock()
    monkeypatch.setattr(service, "build_query_report", query_report)
    monkeypatch.setattr(service, "send_telegram_text", telegram_sender)

    result = send_city_report(
        connection_with_rows([("Hangzhou", 12)]),
    )

    query_report.assert_called_once()
    telegram_sender.assert_called_once_with("固定查询简报")
    assert result == {"status": "sent", "city_count": 1}


def test_send_city_report_defaults_to_query_mode(monkeypatch):
    query_report = Mock(return_value="固定查询简报")
    ai_generator = Mock(return_value="AI 简报")
    sender = Mock()
    monkeypatch.setattr(service, "build_query_report", query_report)

    result = send_city_report(
        connection_with_rows([("Hangzhou", 12)]),
        summary_generator=ai_generator,
        sender=sender,
    )

    query_report.assert_called_once_with([{"city": "Hangzhou", "job_count": 12}])
    ai_generator.assert_not_called()
    sender.assert_called_once_with("固定查询简报")
    assert result == {"status": "sent", "city_count": 1}


def test_send_city_report_uses_ai_mode_when_requested():
    ai_generator = Mock(return_value="AI 简报")
    sender = Mock()

    result = send_city_report(
        connection_with_rows([("Hangzhou", 12)]),
        mode="ai",
        summary_generator=ai_generator,
        sender=sender,
    )

    ai_generator.assert_called_once_with([{"city": "Hangzhou", "job_count": 12}])
    sender.assert_called_once_with("AI 简报")
    assert result == {"status": "sent", "city_count": 1}


def test_send_city_report_rejects_unknown_mode():
    with pytest.raises(ValueError, match="unsupported report mode"):
        send_city_report(
            connection_with_rows([("Hangzhou", 12)]),
            mode="unknown",
            sender=Mock(),
        )


def test_send_city_report_does_not_send_when_openai_fails():
    summary_generator = Mock(side_effect=OpenAISummaryError("OpenAI request failed"))
    sender = Mock()

    with pytest.raises(OpenAISummaryError):
        send_city_report(
            connection_with_rows([("Hangzhou", 12)]),
            mode="ai",
            summary_generator=summary_generator,
            sender=sender,
        )

    sender.assert_not_called()
