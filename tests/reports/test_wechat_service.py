from datetime import date
import hashlib
from unittest.mock import Mock

import pytest

from jobflow.channels.wechat_official import WechatDeliveryUncertain, WechatReceipt
from jobflow.reports.wechat_article import WechatArticleData
from jobflow.reports.wechat_service import (
    generate_wechat_article_from_snapshots,
    get_wechat_article_status,
    get_wechat_daily_report_status,
    send_wechat_daily_report,
    send_wechat_report_from_snapshots,
)


PNG = b"\x89PNG\r\n\x1a\nreport"


def article_data():
    return WechatArticleData(date(2026, 8, 26), 4, 3, (("AI Agent", 10, 2),), ())


def test_service_generates_package_and_records_sent(monkeypatch, tmp_path):
    claim = Mock()
    record = Mock()
    monkeypatch.setattr("jobflow.reports.wechat_service.claim_delivery", claim)
    monkeypatch.setattr("jobflow.reports.wechat_service.record_delivery_result", record)
    connection = Mock()

    result = send_wechat_daily_report(
        connection,
        article_data=article_data(),
        trend_png=PNG,
        output_dir=tmp_path / "wechat",
        token_loader=lambda: "token",
        template_sender=lambda _token, _payload: WechatReceipt(123, 1),
    )

    assert result == {"status": "sent", "message_id": 123}
    assert (tmp_path / "wechat" / "article.html").is_file()
    assert record.call_args.kwargs["status"] == "sent"
    assert connection.commit.call_count == 2


def test_uncertain_send_records_uncertain(monkeypatch, tmp_path):
    monkeypatch.setattr("jobflow.reports.wechat_service.claim_delivery", Mock())
    record = Mock()
    monkeypatch.setattr("jobflow.reports.wechat_service.record_delivery_result", record)
    connection = Mock()

    with pytest.raises(WechatDeliveryUncertain):
        send_wechat_daily_report(
            connection,
            article_data=article_data(),
            trend_png=PNG,
            output_dir=tmp_path / "wechat",
            token_loader=lambda: "token",
            template_sender=lambda _token, _payload: (_ for _ in ()).throw(
                WechatDeliveryUncertain("uncertain")
            ),
        )

    assert record.call_args.kwargs["status"] == "uncertain"


def test_disabled_channel_skips_snapshot_build_and_network(monkeypatch):
    monkeypatch.setenv("WECHAT_ENABLED", "false")
    builder = Mock()
    monkeypatch.setattr("jobflow.reports.wechat_service.build_multi_keyword_wechat_parts", builder)

    result = send_wechat_report_from_snapshots(Mock(), snapshot_date=date(2026, 8, 26))

    assert result["status"] == "disabled"
    builder.assert_not_called()


def test_status_is_safe_when_no_delivery_exists(monkeypatch):
    monkeypatch.setenv("WECHAT_ENABLED", "true")
    monkeypatch.setattr(
        "jobflow.reports.wechat_service.get_channel_delivery", Mock(return_value=None)
    )

    status = get_wechat_daily_report_status(Mock(), snapshot_date=date(2026, 8, 26))

    assert status == {
        "snapshot_date": "2026-08-26",
        "enabled": True,
        "status": "pending",
        "manual_action_required": False,
    }


def test_generate_article_from_snapshots_writes_package_without_network(monkeypatch, tmp_path):
    manifest = Mock(
        new_job_count=2,
        keyword_counts=(("AI Agent", 2), ("Python开发", 0)),
    )
    writer = Mock(return_value=manifest)
    monkeypatch.setattr(
        "jobflow.reports.wechat_service.build_multi_keyword_wechat_parts",
        Mock(return_value=(article_data(), PNG)),
    )
    monkeypatch.setattr(
        "jobflow.reports.wechat_service.build_daily_new_jobs_cover_png",
        Mock(return_value=PNG),
    )
    monkeypatch.setattr("jobflow.reports.wechat_service.write_wechat_article", writer)

    result = generate_wechat_article_from_snapshots(
        Mock(),
        snapshot_date=date(2026, 8, 27),
        runtime_root=tmp_path,
    )

    assert result == {
        "status": "generated",
        "snapshot_date": "2026-08-27",
        "new_job_count": 2,
        "baseline_ready": True,
    }
    assert writer.call_args.args[-1] == tmp_path / "reports" / "2026-08-27" / "wechat"


def test_article_status_distinguishes_pending_and_complete_package(tmp_path):
    pending = get_wechat_article_status(snapshot_date=date(2026, 8, 27), runtime_root=tmp_path)
    assert pending == {"status": "pending", "snapshot_date": "2026-08-27"}

    output = tmp_path / "reports" / "2026-08-27" / "wechat"
    output.mkdir(parents=True)
    for filename in ("article.md", "article.html", "cover.png", "trend.png"):
        (output / filename).write_bytes(b"x")
    digest = hashlib.sha256(b"x").hexdigest()
    (output / "manifest.json").write_text(
        '{"report_date":"2026-08-27","files":["article.md","article.html",'
        '"cover.png","trend.png","manifest.json"],"new_job_count":2,'
        f'"keyword_counts":[["AI Agent",2],["Python开发",null]],'
        f'"cover_sha256":"{digest}","trend_sha256":"{digest}"}}',
        encoding="utf-8",
    )

    generated = get_wechat_article_status(snapshot_date=date(2026, 8, 27), runtime_root=tmp_path)
    assert generated == {
        "status": "generated",
        "snapshot_date": "2026-08-27",
        "new_job_count": 2,
        "baseline_ready": False,
    }
    assert "path" not in generated

    (output / "cover.png").write_bytes(b"tampered")
    corrupted = get_wechat_article_status(snapshot_date=date(2026, 8, 27), runtime_root=tmp_path)
    assert corrupted == {"status": "pending", "snapshot_date": "2026-08-27"}
