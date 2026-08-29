import hashlib
import json
from datetime import date

from jobflow.channels.wechat_draft import UploadedWechatImage
from jobflow.reports.wechat_draft_service import create_wechat_draft_from_article


def _package(tmp_path, report_date):
    cover = b"cover"
    trend = b"trend"
    (tmp_path / "cover.png").write_bytes(cover)
    (tmp_path / "trend.png").write_bytes(trend)
    (tmp_path / "article.html").write_text(
        '<h1>2026-08-29 每日新增岗位公告</h1><img src="trend.png">', encoding="utf-8"
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "report_date": report_date.isoformat(),
                "files": ("article.html", "cover.png", "trend.png", "manifest.json"),
                "cover_sha256": hashlib.sha256(cover).hexdigest(),
                "trend_sha256": hashlib.sha256(trend).hexdigest(),
            }
        ),
        encoding="utf-8",
    )


def test_create_draft_uploads_images_and_records(monkeypatch, tmp_path):
    report_date = date(2026, 8, 29)
    _package(tmp_path, report_date)
    calls = []
    monkeypatch.setattr("jobflow.reports.wechat_draft_service.get_wechat_draft_status", lambda *a, **k: None)
    monkeypatch.setattr("jobflow.reports.wechat_draft_service.claim_wechat_draft", lambda *a, **k: True)
    monkeypatch.setattr("jobflow.reports.wechat_draft_service.get_wechat_access_token", lambda: "token")
    monkeypatch.setattr(
        "jobflow.reports.wechat_draft_service.upload_image",
        lambda **kwargs: UploadedWechatImage(
            "cover" if kwargs["permanent"] else None,
            None if kwargs["permanent"] else "https://img",
        ),
    )
    monkeypatch.setattr("jobflow.reports.wechat_draft_service.create_draft", lambda **kwargs: "draft")
    monkeypatch.setattr("jobflow.reports.wechat_draft_service.record_wechat_draft_created", lambda *a, **k: calls.append(k))
    connection = type("Connection", (), {"commit": lambda self: None})()

    result = create_wechat_draft_from_article(
        connection, report_date=report_date, article_dir=tmp_path, author="OpenJobFlow"
    )

    assert result.status == "created"
    assert result.has_draft is True
    assert calls[0]["draft_media_id"] == "draft"
    assert calls[0]["trend_media_id"] is None


def test_invalid_package_is_recorded_without_network(monkeypatch, tmp_path):
    report_date = date(2026, 8, 29)
    failures = []
    monkeypatch.setattr("jobflow.reports.wechat_draft_service.get_wechat_draft_status", lambda *a, **k: None)
    monkeypatch.setattr("jobflow.reports.wechat_draft_service.claim_wechat_draft", lambda *a, **k: True)
    monkeypatch.setattr("jobflow.reports.wechat_draft_service.record_wechat_draft_failed", lambda *a, **k: failures.append(k))
    monkeypatch.setattr("jobflow.reports.wechat_draft_service.get_wechat_access_token", lambda: (_ for _ in ()).throw(AssertionError()))
    connection = type("Connection", (), {"commit": lambda self: None})()

    result = create_wechat_draft_from_article(
        connection, report_date=report_date, article_dir=tmp_path, author="OpenJobFlow"
    )

    assert result.status == "failed"
    assert result.error_code == "article_package_invalid"
    assert failures[0]["error_code"] == "article_package_invalid"
