from jobflow.reports.query_report import build_query_report


def test_build_query_report_contains_metrics_and_disclaimer():
    report = build_query_report(
        [
            {"city": "杭州", "job_count": 96},
            {"city": "上海", "job_count": 82},
            {"city": "深圳", "job_count": 85},
        ]
    )

    assert "职位总量：263 个" in report
    assert "覆盖城市：3 个" in report
    assert "最高城市岗位数：杭州，96 个" in report
    assert "口径说明" in report
    assert "不代表完整招聘市场规模" in report


def test_build_query_report_contains_ranked_city_table():
    report = build_query_report(
        [
            {"city": "杭州", "job_count": 96},
            {"city": "上海", "job_count": 82},
            {"city": "深圳", "job_count": 85},
        ]
    )

    assert "01" in report
    assert "杭州" in report
    assert "96" in report
    assert "无法判断趋势" in report
