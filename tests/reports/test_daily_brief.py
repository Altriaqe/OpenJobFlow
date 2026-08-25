from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from jobflow.models.snapshot import (
    DailyComparison,
    KeywordTrend,
    MetricChange,
    NamedCount,
    NamedMetric,
    WeeklyComparison,
)
from jobflow.reports.daily_brief import (
    TELEGRAM_MESSAGE_LIMIT,
    _format_direction,
    build_daily_brief,
    build_multi_keyword_brief,
)


def change(current, previous, delta, percent) -> MetricChange:
    return MetricChange(current, previous, delta, percent)


def daily_fixture(*, baseline: bool = True, salary: bool = True) -> DailyComparison:
    previous = 10 if baseline else None
    return DailyComparison(
        has_baseline=baseline,
        total=change(12, previous, 2 if baseline else None, Decimal("20.0") if baseline else None),
        city_metrics=(
            NamedMetric(
                "上海",
                change(
                    5,
                    4 if baseline else None,
                    1 if baseline else None,
                    Decimal("25.0") if baseline else None,
                ),
            ),
            NamedMetric(
                "北京",
                change(
                    3,
                    3 if baseline else None,
                    0 if baseline else None,
                    Decimal("0.0") if baseline else None,
                ),
            ),
            NamedMetric(
                "杭州",
                change(
                    2,
                    2 if baseline else None,
                    0 if baseline else None,
                    Decimal("0.0") if baseline else None,
                ),
            ),
            NamedMetric(
                "深圳",
                change(
                    2,
                    1 if baseline else None,
                    1 if baseline else None,
                    Decimal("100.0") if baseline else None,
                ),
            ),
        ),
        new_count=3 if baseline else None,
        continued_count=9 if baseline else None,
        missing_count=1 if baseline else None,
        skills=(
            NamedMetric(
                "Python",
                change(
                    8,
                    6 if baseline else None,
                    2 if baseline else None,
                    Decimal("33.3") if baseline else None,
                ),
            ),
            NamedMetric(
                "RAG",
                change(
                    5,
                    5 if baseline else None,
                    0 if baseline else None,
                    Decimal("0.0") if baseline else None,
                ),
            ),
        ),
        salary_midpoint_median=(
            change(Decimal("25"), Decimal("23"), Decimal("2"), Decimal("8.7"))
            if salary
            else change(None, None, None, None)
        ),
    )


def weekly_fixture() -> WeeklyComparison:
    daily = daily_fixture()
    return WeeklyComparison(
        current_range=(date(2026, 8, 17), date(2026, 8, 23)),
        previous_range=(date(2026, 8, 10), date(2026, 8, 16)),
        total=daily.total,
        city_metrics=daily.city_metrics,
        skills=daily.skills,
        salary_midpoint_median=daily.salary_midpoint_median,
    )


def multi_keyword_trends(*, has_baseline: bool = True) -> tuple[KeywordTrend, ...]:
    values = (
        ("AI Agent", (5, 2, 1, 0)),
        ("Python开发", (1, 2, 3, 6)),
        ("Java开发", (2, 5, 1, 4)),
        ("数据分析", (3, 2, 7, 1)),
    )
    trends = []
    for keyword, city_counts in values:
        daily = replace(
            daily_fixture(baseline=has_baseline),
            new_count=sum(city_counts) if has_baseline else None,
        )
        new_by_city = (
            tuple(
                NamedCount(city, count)
                for city, count in zip(("上海", "北京", "杭州", "深圳"), city_counts, strict=True)
            )
            if has_baseline
            else None
        )
        trends.append(KeywordTrend(keyword, daily, new_by_city))
    return tuple(trends)


def test_build_daily_brief_uses_management_dashboard_order() -> None:
    report = build_daily_brief(
        report_date=date(2026, 8, 18),
        keyword="AI Agent",
        city_count=4,
        pages_per_city=3,
        daily=daily_fixture(),
    )

    assert report.startswith("━━━━━━━━━━━━━━━━━━\nJobFlow｜AI Agent 招聘市场日报")
    assert report.index("【今日概览】") < report.index("【管理摘要】")
    assert report.index("【管理摘要】") < report.index("【城市表现】")
    assert report.index("【城市表现】") < report.index("【岗位快照变化】")
    assert report.index("【岗位快照变化】") < report.index("【热门技能】")
    assert "范围：4 城市 × 每城 3 页" in report
    assert "本次未出现不代表岗位已经下线" in report
    assert len(report) <= TELEGRAM_MESSAGE_LIMIT


@pytest.mark.parametrize(
    ("metric", "expected"),
    [
        (change(12, 10, 2, Decimal("20.0")), "↑ 2个（↑ 20.0%）"),
        (change(8, 10, -2, Decimal("-20.0")), "↓ 2个（↓ 20.0%）"),
        (change(10, 10, 0, Decimal("0.0")), "持平"),
        (change(10, None, None, None), "暂无历史基准"),
    ],
)
def test_format_direction(metric: MetricChange, expected: str) -> None:
    assert _format_direction(metric) == expected


def test_no_salary_and_no_baseline_are_explicit() -> None:
    report = build_daily_brief(
        report_date=date(2026, 8, 18),
        keyword="AI Agent",
        city_count=4,
        pages_per_city=3,
        daily=daily_fixture(baseline=False, salary=False),
    )

    assert "暂无有效月薪样本" in report
    assert "新增采集：暂无历史基准" in report
    assert "今日采集到 12 个去重岗位" in report


def test_weekly_section_is_appended_only_on_sunday() -> None:
    sunday = build_daily_brief(
        report_date=date(2026, 8, 23),
        keyword="AI Agent",
        city_count=4,
        pages_per_city=3,
        daily=daily_fixture(),
        weekly=weekly_fixture(),
    )
    tuesday = build_daily_brief(
        report_date=date(2026, 8, 18),
        keyword="AI Agent",
        city_count=4,
        pages_per_city=3,
        daily=daily_fixture(),
        weekly=weekly_fixture(),
    )

    assert "【本周趋势｜2026-08-17 至 2026-08-23】" in sunday
    assert "【周度城市变化】" in sunday
    assert "【本周趋势" not in tuesday


def test_report_rejects_content_over_telegram_limit() -> None:
    oversized = replace(
        daily_fixture(),
        skills=(NamedMetric("超长技能" * 700, change(1, 1, 0, Decimal("0.0"))),),
    )

    with pytest.raises(ValueError, match="Telegram message limit"):
        build_daily_brief(
            report_date=date(2026, 8, 18),
            keyword="AI Agent",
            city_count=4,
            pages_per_city=3,
            daily=oversized,
        )


def test_build_multi_keyword_brief_shows_keyword_and_city_advantages() -> None:
    report = build_multi_keyword_brief(
        report_date=date(2026, 8, 21),
        trends=multi_keyword_trends(),
        city_count=4,
        pages_per_city=3,
    )

    assert report.startswith("━━━━━━━━━━━━━━━━━━\nJobFlow｜多岗位招聘趋势日报")
    assert "【岗位趋势】" in report
    assert "AI Agent：较昨日新增采集 8 个" in report
    assert "新增最多城市：上海（5 个）" in report
    assert "【城市优势】" in report
    assert "上海：AI Agent新增样本最多（5 个）" in report
    assert "4 个关键词 × 4 个城市 × 每组 3 页" in report
    assert "不代表全市场总量" in report
    assert len(report) <= TELEGRAM_MESSAGE_LIMIT


def test_build_multi_keyword_brief_marks_baseline_pending() -> None:
    report = build_multi_keyword_brief(
        report_date=date(2026, 8, 20),
        trends=multi_keyword_trends(has_baseline=False),
        city_count=4,
        pages_per_city=3,
    )

    assert "趋势基线建立中" in report
    assert "新增最多城市" not in report


def test_multi_keyword_weekly_section_requires_all_keyword_baselines() -> None:
    complete = tuple(replace(trend, weekly=weekly_fixture()) for trend in multi_keyword_trends())
    complete_report = build_multi_keyword_brief(
        report_date=date(2026, 8, 23),
        trends=complete,
        city_count=4,
        pages_per_city=3,
    )
    incomplete_report = build_multi_keyword_brief(
        report_date=date(2026, 8, 23),
        trends=multi_keyword_trends(),
        city_count=4,
        pages_per_city=3,
    )

    assert "【周趋势】" in complete_report
    assert "AI Agent：↑ 2个（↑ 20.0%）" in complete_report
    assert "周趋势数据不足" in incomplete_report
