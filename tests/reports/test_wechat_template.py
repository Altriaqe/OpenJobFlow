from datetime import date

from jobflow.reports.wechat_article import WechatArticleData
from jobflow.reports.wechat_template import build_wechat_template_data


def test_template_data_uses_aggregate_metrics_and_stable_ties():
    data = WechatArticleData(
        report_date=date(2026, 8, 26),
        city_count=4,
        pages_per_city=3,
        keyword_rows=(("Python开发", 20, 3), ("AI Agent", 20, 2)),
        city_advantages=(("上海", "AI Agent", 5), ("北京", "Python开发", 7)),
    )

    payload = build_wechat_template_data(data)

    assert payload["total_jobs"]["value"] == "40"
    assert payload["new_jobs"]["value"] == "5"
    assert payload["top_keyword"]["value"] == "AI Agent（20）"
    assert payload["top_city"]["value"] == "Python开发 / 北京（7）"


def test_template_data_marks_incomplete_baseline_and_cleans_fields():
    data = WechatArticleData(
        report_date=date(2026, 8, 26),
        city_count=4,
        pages_per_city=3,
        keyword_rows=(("AI\nAgent", 10, None),),
        city_advantages=(),
    )

    payload = build_wechat_template_data(data)

    assert payload["new_jobs"]["value"] == "基线建立中"
    assert payload["top_city"]["value"] == "基线建立中"
    assert "\n" not in payload["top_keyword"]["value"]
    assert all(len(field["value"]) <= 80 for field in payload.values())
