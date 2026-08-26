"""日环比和周环比计算层：只比较采集口径一致的快照。"""

from collections import Counter
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from jobflow.models.snapshot import (
    DailyComparison,
    DatedSnapshot,
    MetricChange,
    NamedCount,
    NamedMetric,
    SnapshotItem,
    WeeklyComparison,
)

_ONE_DECIMAL = Decimal("0.1")


def _index_items(items: Sequence[SnapshotItem]) -> dict[tuple[str, str], SnapshotItem]:
    indexed: dict[tuple[str, str], SnapshotItem] = {}
    for item in items:
        if item.identity in indexed:
            raise ValueError(f"duplicate snapshot identity: {item.identity!r}")
        indexed[item.identity] = item
    return indexed


def count_new_jobs_by_city(
    current: Sequence[SnapshotItem],
    previous: Sequence[SnapshotItem] | None,
    *,
    cities: Sequence[str],
) -> tuple[NamedCount, ...] | None:
    ordered_cities = tuple(cities)
    if not ordered_cities or len(set(ordered_cities)) != len(ordered_cities):
        raise ValueError("cities must be non-empty and unique")
    if previous is None:
        return None

    current_by_identity = _index_items(current)
    previous_by_identity = _index_items(previous)
    allowed_cities = set(ordered_cities)
    unknown_cities = sorted(
        {
            item.city
            for item in (*current_by_identity.values(), *previous_by_identity.values())
            if item.city not in allowed_cities
        }
    )
    if unknown_cities:
        raise ValueError(f"snapshot contains undeclared cities: {unknown_cities!r}")

    previous_identities = set(previous_by_identity)
    counts = Counter(
        item.city
        for identity, item in current_by_identity.items()
        if identity not in previous_identities
    )
    return tuple(NamedCount(city, counts[city]) for city in ordered_cities)


def _change(
    current: int | Decimal | None,
    previous: int | Decimal | None,
    *,
    has_baseline: bool,
) -> MetricChange:
    if not has_baseline:
        return MetricChange(current=current, previous=None, delta=None, percent=None)
    if previous is None or current is None:
        return MetricChange(current=current, previous=previous, delta=None, percent=None)

    delta = current - previous
    percent = None
    if previous != 0:
        percent = (Decimal(delta) / Decimal(previous) * Decimal(100)).quantize(_ONE_DECIMAL)
    return MetricChange(current=current, previous=previous, delta=delta, percent=percent)


def _skill_counts(items: Sequence[SnapshotItem]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in items:
        normalized = {skill.strip() for skill in item.skills if skill.strip()}
        counts.update(normalized)
    return counts


def _monthly_salary_midpoint(item: SnapshotItem) -> Decimal | None:
    if (
        item.salary_min is None
        or item.salary_max is None
        or item.salary_min <= 0
        or item.salary_max < item.salary_min
    ):
        return None

    if item.salary_unit == "K_PER_MONTH":
        divisor = Decimal(1)
    elif item.salary_unit == "CNY_PER_MONTH":
        divisor = Decimal(1000)
    else:
        return None

    return (Decimal(item.salary_min) + Decimal(item.salary_max)) / Decimal(2) / divisor


def _salary_median(items: Sequence[SnapshotItem]) -> Decimal | None:
    midpoints = [
        midpoint for item in items if (midpoint := _monthly_salary_midpoint(item)) is not None
    ]
    return median(midpoints) if midpoints else None


def compare_daily(
    current: Sequence[SnapshotItem],
    previous: Sequence[SnapshotItem] | None,
    *,
    cities: Sequence[str],
    skill_limit: int = 5,
) -> DailyComparison:
    """按岗位身份比较当天快照与前一自然日的同口径快照。"""

    if skill_limit < 0:
        raise ValueError("skill_limit must not be negative")
    if not cities or len(set(cities)) != len(cities):
        raise ValueError("cities must be non-empty and unique")

    current_by_id = _index_items(current)
    previous_by_id = None if previous is None else _index_items(previous)
    allowed_cities = set(cities)
    all_items = tuple(current) + (() if previous is None else tuple(previous))
    unknown_cities = sorted({item.city for item in all_items if item.city not in allowed_cities})
    if unknown_cities:
        raise ValueError(f"snapshot contains undeclared cities: {unknown_cities!r}")

    has_baseline = previous_by_id is not None
    previous_items = () if previous is None else tuple(previous)
    previous_count = None if previous is None else len(previous_by_id)
    total = _change(len(current_by_id), previous_count, has_baseline=has_baseline)

    city_metrics = tuple(
        NamedMetric(
            city,
            _change(
                sum(item.city == city for item in current),
                None if previous is None else sum(item.city == city for item in previous_items),
                has_baseline=has_baseline,
            ),
        )
        for city in cities
    )

    current_skills = _skill_counts(current)
    previous_skills = _skill_counts(previous_items)
    top_skills = sorted(current_skills, key=lambda name: (-current_skills[name], name))[
        :skill_limit
    ]
    skills = tuple(
        NamedMetric(
            name,
            _change(
                current_skills[name],
                None if previous is None else previous_skills[name],
                has_baseline=has_baseline,
            ),
        )
        for name in top_skills
    )

    salary = _change(
        _salary_median(current),
        None if previous is None else _salary_median(previous_items),
        has_baseline=has_baseline,
    )

    if previous_by_id is None:
        new_count = continued_count = missing_count = None
    else:
        current_ids = set(current_by_id)
        previous_ids = set(previous_by_id)
        new_count = len(current_ids - previous_ids)
        continued_count = len(current_ids & previous_ids)
        missing_count = len(previous_ids - current_ids)

    return DailyComparison(
        has_baseline=has_baseline,
        total=total,
        city_metrics=city_metrics,
        new_count=new_count,
        continued_count=continued_count,
        missing_count=missing_count,
        skills=skills,
        salary_midpoint_median=salary,
    )


def _week_dates(sunday: date) -> tuple[date, ...]:
    monday = sunday - timedelta(days=6)
    return tuple(monday + timedelta(days=offset) for offset in range(7))


def _validate_complete_week(days: Sequence[DatedSnapshot], expected: tuple[date, ...]) -> bool:
    actual = [day.snapshot_date for day in days]
    return len(actual) == 7 and len(set(actual)) == 7 and set(actual) == set(expected)


def _collapse_week(days: Sequence[DatedSnapshot]) -> tuple[SnapshotItem, ...]:
    latest: dict[tuple[str, str], SnapshotItem] = {}
    for day in sorted(days, key=lambda value: value.snapshot_date):
        for identity, item in _index_items(day.items).items():
            latest[identity] = item
    return tuple(latest.values())


def compare_complete_weeks(
    *,
    report_date: date,
    current_days: Sequence[DatedSnapshot],
    previous_days: Sequence[DatedSnapshot],
    cities: Sequence[str],
    skill_limit: int = 5,
) -> WeeklyComparison | None:
    """仅在周日比较两个资料完整的自然周。"""

    if report_date.weekday() != 6:
        return None

    current_dates = _week_dates(report_date)
    previous_dates = _week_dates(report_date - timedelta(days=7))
    if not _validate_complete_week(current_days, current_dates):
        return None
    if not _validate_complete_week(previous_days, previous_dates):
        return None

    daily = compare_daily(
        _collapse_week(current_days),
        _collapse_week(previous_days),
        cities=cities,
        skill_limit=skill_limit,
    )
    return WeeklyComparison(
        current_range=(current_dates[0], current_dates[-1]),
        previous_range=(previous_dates[0], previous_dates[-1]),
        total=daily.total,
        city_metrics=daily.city_metrics,
        skills=daily.skills,
        salary_midpoint_median=daily.salary_midpoint_median,
    )
