from datetime import date, timedelta
from decimal import Decimal

import pytest

from jobflow.models.snapshot import DatedSnapshot, MetricChange, SnapshotItem
from jobflow.reports.comparison import (
    compare_complete_weeks,
    compare_daily,
    count_new_jobs_by_city,
)

CITIES = ("上海", "北京", "杭州", "深圳")


def item(
    external_id: str,
    *,
    city: str = "上海",
    salary: tuple[int, int] | None = (20, 30),
    salary_unit: str = "K_PER_MONTH",
    skills: tuple[str, ...] = ("Python",),
) -> SnapshotItem:
    return SnapshotItem(
        source="boss_zhipin",
        external_id=external_id,
        title=f"岗位 {external_id}",
        company="示例公司",
        city=city,
        salary_min=None if salary is None else salary[0],
        salary_max=None if salary is None else salary[1],
        salary_unit=salary_unit,
        skills=skills,
    )


def test_daily_comparison_counts_identity_city_skill_and_salary() -> None:
    current = (
        item("a", skills=("Python", "Python")),
        item("b", city="北京", salary=(10, 20), skills=("RAG",)),
        item("c", city="杭州", salary=(30, 40), skills=("Python",)),
    )
    previous = (item("a"), item("b", city="北京"), item("d", city="深圳"))

    result = compare_daily(current, previous, cities=CITIES)

    assert result.total == MetricChange(3, 3, 0, Decimal("0.0"))
    assert (result.new_count, result.continued_count, result.missing_count) == (1, 2, 1)
    assert tuple(metric.name for metric in result.city_metrics) == CITIES
    assert result.city_metrics[0].change.current == 1
    assert result.salary_midpoint_median.current == Decimal("25")
    assert result.skills[0].name == "Python"
    assert result.skills[0].change.current == 2


def test_daily_without_baseline_keeps_only_current_values() -> None:
    result = compare_daily((item("a"), item("b")), None, cities=CITIES)

    assert result.has_baseline is False
    assert result.total == MetricChange(2, None, None, None)
    assert result.new_count is None
    assert result.salary_midpoint_median == MetricChange(Decimal("25"), None, None, None)


def test_count_new_jobs_by_city_uses_identity_and_preserves_city_order() -> None:
    previous = (
        item("old-sh", city="上海"),
        item("old-bj", city="北京"),
    )
    current = (
        item("old-sh", city="上海"),
        item("new-sh-1", city="上海"),
        item("new-sh-2", city="上海"),
        item("new-bj", city="北京"),
    )

    result = count_new_jobs_by_city(current, previous, cities=CITIES)

    assert result is not None
    assert [(metric.name, metric.count) for metric in result] == [
        ("上海", 2),
        ("北京", 1),
        ("杭州", 0),
        ("深圳", 0),
    ]


def test_count_new_jobs_by_city_returns_none_without_baseline() -> None:
    assert count_new_jobs_by_city((item("new-sh"),), None, cities=CITIES) is None


def test_count_new_jobs_by_city_rejects_undeclared_city() -> None:
    with pytest.raises(ValueError, match="undeclared cities"):
        count_new_jobs_by_city(
            (item("new-gz", city="广州"),),
            (),
            cities=CITIES,
        )


def test_zero_baseline_has_delta_but_no_percentage() -> None:
    result = compare_daily((item("a"), item("b")), (), cities=CITIES)

    assert result.total == MetricChange(2, 0, 2, None)


def test_salary_uses_monthly_valid_ranges_only() -> None:
    current = (
        item("a", salary=(10, 20)),
        item("b", salary=(20, 30)),
        item("c", salary=(30, 20)),
        item("d", salary=(100, 200), salary_unit="YUAN_PER_DAY"),
        item("e", salary=None),
    )
    result = compare_daily(current, (), cities=CITIES)

    assert result.salary_midpoint_median.current == Decimal("20")


def test_salary_normalizes_cny_monthly_values_to_k() -> None:
    current = (
        item("k-monthly", salary=(10, 20), salary_unit="K_PER_MONTH"),
        item("cny-monthly", salary=(3500, 5500), salary_unit="CNY_PER_MONTH"),
    )

    result = compare_daily(current, (), cities=CITIES)

    assert result.salary_midpoint_median.current == Decimal("9.75")


def test_no_valid_salary_samples_returns_none() -> None:
    result = compare_daily(
        (item("a", salary=(100, 200), salary_unit="YUAN_PER_DAY"),),
        (item("b", salary=(20, 30), salary_unit="YUAN_PER_HOUR"),),
        cities=CITIES,
    )

    assert result.salary_midpoint_median == MetricChange(None, None, None, None)


@pytest.mark.parametrize(
    "items",
    [
        (item("a"), item("a")),
        (item("a"), item("b", city="广州")),
    ],
)
def test_daily_rejects_invalid_snapshot_members(items: tuple[SnapshotItem, ...]) -> None:
    with pytest.raises(ValueError):
        compare_daily(items, None, cities=CITIES)


def make_week(monday: date, daily_items: tuple[SnapshotItem, ...]) -> tuple[DatedSnapshot, ...]:
    return tuple(DatedSnapshot(monday + timedelta(days=offset), daily_items) for offset in range(7))


def test_complete_week_deduplicates_jobs_and_uses_last_observation() -> None:
    current_monday = date(2026, 8, 17)
    previous_monday = date(2026, 8, 10)
    current = list(make_week(current_monday, (item("a", salary=(10, 20)),)))
    current[-1] = DatedSnapshot(
        date(2026, 8, 23),
        (item("a", salary=(30, 40), skills=("SundaySkill",)), item("b", city="北京")),
    )
    previous = make_week(previous_monday, (item("a", salary=(10, 20)),))

    result = compare_complete_weeks(
        report_date=date(2026, 8, 23),
        current_days=current,
        previous_days=previous,
        cities=CITIES,
    )

    assert result is not None
    assert result.current_range == (date(2026, 8, 17), date(2026, 8, 23))
    assert result.previous_range == (date(2026, 8, 10), date(2026, 8, 16))
    assert result.total.current == 2
    assert result.salary_midpoint_median.current == Decimal("30")
    assert "SundaySkill" in {metric.name for metric in result.skills}


def test_missing_current_salary_keeps_baseline_without_inventing_change() -> None:
    result = compare_daily(
        (item("a", salary=None),),
        (item("a", salary=(10, 20)),),
        cities=CITIES,
    )

    assert result.salary_midpoint_median == MetricChange(None, Decimal("15"), None, None)


def test_weekly_comparison_normalizes_cny_monthly_values_to_k() -> None:
    current = make_week(
        date(2026, 8, 17),
        (item("cny-monthly", salary=(3500, 5500), salary_unit="CNY_PER_MONTH"),),
    )
    previous = make_week(
        date(2026, 8, 10),
        (item("k-monthly", salary=(5, 7), salary_unit="K_PER_MONTH"),),
    )

    result = compare_complete_weeks(
        report_date=date(2026, 8, 23),
        current_days=current,
        previous_days=previous,
        cities=CITIES,
    )

    assert result is not None
    assert result.salary_midpoint_median.current == Decimal("4.5")
    assert result.salary_midpoint_median.previous == Decimal("6")


def test_weekly_comparison_requires_sunday_and_every_natural_date() -> None:
    current = list(make_week(date(2026, 8, 17), (item("a"),)))
    previous = make_week(date(2026, 8, 10), (item("b"),))

    assert (
        compare_complete_weeks(
            report_date=date(2026, 8, 22),
            current_days=current,
            previous_days=previous,
            cities=CITIES,
        )
        is None
    )
    del current[2]
    assert (
        compare_complete_weeks(
            report_date=date(2026, 8, 23),
            current_days=current,
            previous_days=previous,
            cities=CITIES,
        )
        is None
    )


def test_complete_week_supports_year_boundary() -> None:
    current = make_week(date(2025, 12, 29), (item("a"),))
    previous = make_week(date(2025, 12, 22), (item("b"),))

    result = compare_complete_weeks(
        report_date=date(2026, 1, 4),
        current_days=current,
        previous_days=previous,
        cities=CITIES,
    )

    assert result is not None
    assert result.current_range == (date(2025, 12, 29), date(2026, 1, 4))
