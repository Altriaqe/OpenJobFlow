from datetime import date
import json

import pytest

from jobflow.models.snapshot import DailyComparison, KeywordTrend, MetricChange
from jobflow.reports.wechat_article import (
    WechatArticleData,
    build_article_data,
    write_wechat_article,
)


PNG = b"\x89PNG\r\n\x1a\narticle"


def sample_data() -> WechatArticleData:
    return WechatArticleData(
        report_date=date(2026, 8, 26),
        city_count=4,
        pages_per_city=3,
        keyword_rows=(("AI Agent", 18, 3), ("Python开发", 21, None)),
        city_advantages=(("上海", "AI Agent", 5), ("北京", "Python开发", 7)),
        weekly_summary=None,
    )


def test_article_package_contains_four_deterministic_files(tmp_path):
    manifest = write_wechat_article(sample_data(), PNG, tmp_path / "wechat")

    assert manifest.files == ("article.md", "article.html", "trend.png", "manifest.json")
    assert (tmp_path / "wechat" / "trend.png").read_bytes() == PNG
    assert "固定范围样本" in (tmp_path / "wechat" / "article.md").read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "wechat" / "manifest.json").read_text(encoding="utf-8"))
    assert payload["report_date"] == "2026-08-26"


def test_html_has_no_script_remote_resource_or_sensitive_fields(tmp_path):
    write_wechat_article(sample_data(), PNG, tmp_path / "wechat")
    html = (tmp_path / "wechat" / "article.html").read_text(encoding="utf-8")

    assert "<script" not in html.lower()
    assert "http://" not in html.lower()
    assert "https://" not in html.lower()
    assert "openid" not in html.lower()
    assert "appsecret" not in html.lower()
    assert 'src="trend.png"' in html


def test_invalid_image_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="PNG"):
        write_wechat_article(sample_data(), b"not-an-image", tmp_path / "wechat")


def test_build_article_data_reuses_keyword_trend_metrics():
    daily = DailyComparison(
        has_baseline=True,
        total=MetricChange(10, 8, 2, None),
        city_metrics=(),
        new_count=2,
        continued_count=None,
        missing_count=None,
        skills=(),
        salary_midpoint_median=MetricChange(None, None, None, None),
    )
    trends = (KeywordTrend("AI Agent", daily, None),)

    data = build_article_data(
        report_date=date(2026, 8, 26), trends=trends, city_count=4, pages_per_city=3
    )

    assert data.keyword_rows == (("AI Agent", 10, 2),)


def test_article_package_can_be_replaced_as_a_complete_directory(tmp_path):
    output = tmp_path / "wechat"
    write_wechat_article(sample_data(), PNG, output)
    (output / "stale.txt").write_text("old", encoding="utf-8")

    write_wechat_article(sample_data(), PNG, output)

    assert not (output / "stale.txt").exists()
    assert {path.name for path in output.iterdir()} == {
        "article.md",
        "article.html",
        "trend.png",
        "manifest.json",
    }
