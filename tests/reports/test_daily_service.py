from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest

from jobflow.channels.telegram import TelegramDeliveryError, TelegramReceipt
from jobflow.models.snapshot import (
    DailyComparison,
    MetricChange,
    NamedMetric,
    ReportDelivery,
    SnapshotHeader,
)
from jobflow.reports import daily_service

REPORT_DATE = date(2026, 8, 18)
CITIES = ("上海", "北京", "杭州", "深圳")


def header(
    *,
    snapshot_id: int = 17,
    snapshot_date: date = REPORT_DATE,
    pages: int = 3,
) -> SnapshotHeader:
    return SnapshotHeader(
        id=snapshot_id,
        snapshot_date=snapshot_date,
        search_keyword="AI Agent",
        batch_id=42,
        city_count=4,
        cities=CITIES,
        pages_per_city=pages,
        details_included=False,
    )


def delivery(status: str = "pending", *, text_message_id: int | None = None) -> ReportDelivery:
    return ReportDelivery(
        snapshot_id=17,
        status=status,
        text_message_id=text_message_id,
        photo_message_id=None,
        text_attempts=0,
        photo_attempts=0,
        last_error_type=None,
    )


def comparison(*, baseline: bool = False) -> DailyComparison:
    metric = MetricChange(
        4, 3 if baseline else None, 1 if baseline else None, Decimal("33.3") if baseline else None
    )
    cities = tuple(NamedMetric(city, MetricChange(1, None, None, None)) for city in CITIES)
    return DailyComparison(
        has_baseline=baseline,
        total=metric,
        city_metrics=cities,
        new_count=1 if baseline else None,
        continued_count=3 if baseline else None,
        missing_count=0 if baseline else None,
        skills=(),
        salary_midpoint_median=MetricChange(None, None, None, None),
    )


def arrange(
    monkeypatch,
    *,
    state: ReportDelivery | None = None,
    previous: SnapshotHeader | None = None,
) -> tuple[Mock, Mock]:
    current = header()

    def get_snapshot(_connection, *, snapshot_date, search_keyword):
        assert search_keyword == "AI Agent"
        if snapshot_date == REPORT_DATE:
            return current
        if snapshot_date == REPORT_DATE - timedelta(days=1):
            return previous
        return None

    monkeypatch.setattr(daily_service, "get_snapshot", get_snapshot)
    monkeypatch.setattr(daily_service, "get_delivery", lambda *_args: state or delivery())
    list_items = Mock(return_value=())
    monkeypatch.setattr(daily_service, "list_snapshot_items", list_items)
    compare = Mock(
        return_value=comparison(baseline=previous is not None and previous.pages_per_city == 3)
    )
    monkeypatch.setattr(daily_service, "compare_daily", compare)
    monkeypatch.setattr(daily_service, "build_daily_brief", Mock(return_value="简报"))
    monkeypatch.setattr(daily_service, "build_city_share_png", Mock(return_value=b"png"))
    monkeypatch.setattr(daily_service, "record_text_sent", Mock())
    monkeypatch.setattr(daily_service, "record_photo_sent", Mock())
    monkeypatch.setattr(daily_service, "record_text_failure", Mock())
    monkeypatch.setattr(daily_service, "record_photo_failure", Mock())
    return list_items, compare


def test_send_daily_report_sends_text_then_photo_and_records_ids(monkeypatch) -> None:
    arrange(monkeypatch)
    connection = Mock()
    events: list[str] = []
    text_sender = Mock(side_effect=lambda _text: events.append("text") or TelegramReceipt(101, 1))
    photo_sender = Mock(
        side_effect=lambda _image: events.append("photo") or TelegramReceipt(202, 1)
    )

    result = daily_service.send_daily_report(
        connection,
        snapshot_date=REPORT_DATE,
        keyword="AI Agent",
        text_sender=text_sender,
        photo_sender=photo_sender,
    )

    assert events == ["text", "photo"]
    assert result == {
        "status": "sent",
        "snapshot_id": 17,
        "text_message_id": 101,
        "photo_message_id": 202,
    }
    daily_service.record_text_sent.assert_called_once_with(connection, 17, 101, 1)
    daily_service.record_photo_sent.assert_called_once_with(connection, 17, 202, 1)
    assert connection.commit.call_count == 2


def test_send_daily_report_resumes_photo_without_duplicate_text(monkeypatch) -> None:
    arrange(monkeypatch, state=delivery("partial_failed", text_message_id=101))
    text_sender = Mock()
    photo_sender = Mock(return_value=TelegramReceipt(303, 1))

    result = daily_service.send_daily_report(
        Mock(),
        snapshot_date=REPORT_DATE,
        keyword="AI Agent",
        text_sender=text_sender,
        photo_sender=photo_sender,
    )

    text_sender.assert_not_called()
    photo_sender.assert_called_once()
    assert result["status"] == "sent"
    assert result["text_message_id"] == 101


def test_missing_snapshot_raises_not_found(monkeypatch) -> None:
    monkeypatch.setattr(daily_service, "get_snapshot", lambda *_args, **_kwargs: None)
    text_sender = Mock()
    photo_sender = Mock()

    with pytest.raises(daily_service.DailySnapshotNotFound):
        daily_service.send_daily_report(
            Mock(),
            snapshot_date=REPORT_DATE,
            keyword="AI Agent",
            text_sender=text_sender,
            photo_sender=photo_sender,
        )

    text_sender.assert_not_called()
    photo_sender.assert_not_called()


def test_completed_delivery_returns_without_rendering_or_external_calls(monkeypatch) -> None:
    arrange(monkeypatch, state=delivery("completed", text_message_id=101))
    formatter = Mock()
    chart = Mock()
    monkeypatch.setattr(daily_service, "build_daily_brief", formatter)
    monkeypatch.setattr(daily_service, "build_city_share_png", chart)
    text_sender = Mock()
    photo_sender = Mock()

    result = daily_service.send_daily_report(
        Mock(),
        snapshot_date=REPORT_DATE,
        keyword="AI Agent",
        text_sender=text_sender,
        photo_sender=photo_sender,
    )

    assert result == {"status": "already_sent", "snapshot_id": 17}
    formatter.assert_not_called()
    chart.assert_not_called()
    text_sender.assert_not_called()
    photo_sender.assert_not_called()


def test_chart_failure_prevents_any_external_send(monkeypatch) -> None:
    arrange(monkeypatch)
    monkeypatch.setattr(
        daily_service, "build_city_share_png", Mock(side_effect=ValueError("invalid chart"))
    )
    text_sender = Mock()
    photo_sender = Mock()

    with pytest.raises(ValueError, match="invalid chart"):
        daily_service.send_daily_report(
            Mock(),
            snapshot_date=REPORT_DATE,
            keyword="AI Agent",
            text_sender=text_sender,
            photo_sender=photo_sender,
        )

    text_sender.assert_not_called()
    photo_sender.assert_not_called()


def test_text_failure_records_failed_and_commits(monkeypatch) -> None:
    arrange(monkeypatch)
    connection = Mock()
    photo_sender = Mock()

    with pytest.raises(TelegramDeliveryError) as exc_info:
        daily_service.send_daily_report(
            connection,
            snapshot_date=REPORT_DATE,
            keyword="AI Agent",
            text_sender=Mock(side_effect=TelegramDeliveryError("secret", attempts=3)),
            photo_sender=photo_sender,
        )

    assert exc_info.value.attempts == 3
    assert "secret" not in str(exc_info.value)
    daily_service.record_text_failure.assert_called_once_with(
        connection, 17, "telegram_delivery", 3
    )
    connection.commit.assert_called_once_with()
    photo_sender.assert_not_called()


def test_photo_failure_records_partial_failed_after_text_commit(monkeypatch) -> None:
    arrange(monkeypatch)
    connection = Mock()

    with pytest.raises(TelegramDeliveryError):
        daily_service.send_daily_report(
            connection,
            snapshot_date=REPORT_DATE,
            keyword="AI Agent",
            text_sender=Mock(return_value=TelegramReceipt(101, 1)),
            photo_sender=Mock(side_effect=TelegramDeliveryError("secret", attempts=2)),
        )

    daily_service.record_text_sent.assert_called_once_with(connection, 17, 101, 1)
    daily_service.record_photo_failure.assert_called_once_with(
        connection, 17, "telegram_delivery", 2
    )
    assert connection.commit.call_count == 2


def test_missing_previous_day_does_not_load_an_older_snapshot(monkeypatch) -> None:
    list_items, compare = arrange(monkeypatch, previous=None)

    daily_service.send_daily_report(
        Mock(),
        snapshot_date=REPORT_DATE,
        keyword="AI Agent",
        text_sender=Mock(return_value=TelegramReceipt(101, 1)),
        photo_sender=Mock(return_value=TelegramReceipt(202, 1)),
    )

    list_items.assert_called_once_with(list_items.call_args.args[0], 17)
    assert compare.call_args.args[1] is None


def test_different_page_scope_is_not_used_as_baseline(monkeypatch) -> None:
    _list_items, compare = arrange(
        monkeypatch,
        previous=header(snapshot_id=16, snapshot_date=REPORT_DATE - timedelta(days=1), pages=1),
    )

    daily_service.send_daily_report(
        Mock(),
        snapshot_date=REPORT_DATE,
        keyword="AI Agent",
        text_sender=Mock(return_value=TelegramReceipt(101, 1)),
        photo_sender=Mock(return_value=TelegramReceipt(202, 1)),
    )

    assert compare.call_args.args[1] is None


def test_sunday_loads_exact_two_monday_to_sunday_ranges(monkeypatch) -> None:
    report_date = date(2026, 8, 23)
    current = header(snapshot_date=report_date)

    def get_snapshot(_connection, *, snapshot_date, search_keyword):
        return SnapshotHeader(
            **{**current.__dict__, "id": snapshot_date.toordinal(), "snapshot_date": snapshot_date}
        )

    monkeypatch.setattr(daily_service, "get_snapshot", get_snapshot)
    monkeypatch.setattr(daily_service, "get_delivery", lambda *_args: delivery())
    monkeypatch.setattr(daily_service, "list_snapshot_items", Mock(return_value=()))
    monkeypatch.setattr(daily_service, "compare_daily", Mock(return_value=comparison()))
    ranges: list[tuple[date, date]] = []

    def list_days(_connection, *, start_date, end_date, search_keyword):
        ranges.append((start_date, end_date))
        return ()

    monkeypatch.setattr(daily_service, "list_dated_snapshots", list_days)
    monkeypatch.setattr(daily_service, "compare_complete_weeks", Mock(return_value=None))
    monkeypatch.setattr(daily_service, "build_daily_brief", Mock(return_value="简报"))
    monkeypatch.setattr(daily_service, "build_city_share_png", Mock(return_value=b"png"))
    monkeypatch.setattr(daily_service, "record_text_sent", Mock())
    monkeypatch.setattr(daily_service, "record_photo_sent", Mock())

    daily_service.send_daily_report(
        Mock(),
        snapshot_date=report_date,
        keyword="AI Agent",
        text_sender=Mock(return_value=TelegramReceipt(101, 1)),
        photo_sender=Mock(return_value=TelegramReceipt(202, 1)),
    )

    assert ranges == [
        (date(2026, 8, 17), date(2026, 8, 23)),
        (date(2026, 8, 10), date(2026, 8, 16)),
    ]
