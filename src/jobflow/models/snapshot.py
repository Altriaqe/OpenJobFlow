from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class SnapshotMetadata:
    """描述一份正式岗位快照的采集范围。"""

    snapshot_date: date
    search_keyword: str
    cities: tuple[str, ...]
    pages_per_city: int
    details_included: bool

    def __post_init__(self) -> None:
        keyword = self.search_keyword.strip()
        cities = tuple(city.strip() for city in self.cities)

        if not keyword:
            raise ValueError("search_keyword must not be empty")
        if not cities or any(not city for city in cities):
            raise ValueError("cities must be non-empty")
        if len(set(cities)) != len(cities):
            raise ValueError("cities must be unique")
        if self.pages_per_city <= 0:
            raise ValueError("pages_per_city must be positive")

        object.__setattr__(self, "search_keyword", keyword)
        object.__setattr__(self, "cities", cities)

    @property
    def city_count(self) -> int:
        return len(self.cities)

    @property
    def scope_key(self) -> tuple[str, tuple[str, ...], int, bool]:
        """返回用于判断两个快照能否比较的采集口径。"""

        return (
            self.search_keyword,
            tuple(sorted(self.cities)),
            self.pages_per_city,
            self.details_included,
        )


@dataclass(frozen=True)
class SnapshotItem:
    """一份每日快照中的不可变岗位观察值。"""

    source: str
    external_id: str
    title: str
    company: str
    city: str
    salary_min: int | None = None
    salary_max: int | None = None
    salary_unit: str | None = None
    skills: tuple[str, ...] = ()

    @property
    def identity(self) -> tuple[str, str]:
        return self.source, self.external_id


@dataclass(frozen=True)
class MetricChange:
    """一个指标的本期值、基准值和变化。"""

    current: int | Decimal | None
    previous: int | Decimal | None
    delta: int | Decimal | None
    percent: Decimal | None


@dataclass(frozen=True)
class NamedMetric:
    name: str
    change: MetricChange


@dataclass(frozen=True)
class NamedCount:
    name: str
    count: int

    def __post_init__(self) -> None:
        name = self.name.strip()
        if not name:
            raise ValueError("name must not be empty")
        if self.count < 0:
            raise ValueError("count must not be negative")
        object.__setattr__(self, "name", name)


@dataclass(frozen=True)
class DailyComparison:
    has_baseline: bool
    total: MetricChange
    city_metrics: tuple[NamedMetric, ...]
    new_count: int | None
    continued_count: int | None
    missing_count: int | None
    skills: tuple[NamedMetric, ...]
    salary_midpoint_median: MetricChange


@dataclass(frozen=True)
class DatedSnapshot:
    snapshot_date: date
    items: tuple[SnapshotItem, ...]


@dataclass(frozen=True)
class WeeklyComparison:
    current_range: tuple[date, date]
    previous_range: tuple[date, date]
    total: MetricChange
    city_metrics: tuple[NamedMetric, ...]
    skills: tuple[NamedMetric, ...]
    salary_midpoint_median: MetricChange


@dataclass(frozen=True)
class KeywordTrend:
    keyword: str
    daily: DailyComparison
    new_by_city: tuple[NamedCount, ...] | None
    weekly: WeeklyComparison | None = None

    def __post_init__(self) -> None:
        keyword = self.keyword.strip()
        if not keyword:
            raise ValueError("keyword must not be empty")
        object.__setattr__(self, "keyword", keyword)


@dataclass(frozen=True)
class SnapshotHeader:
    id: int
    snapshot_date: date
    search_keyword: str
    batch_id: int
    city_count: int
    cities: tuple[str, ...]
    pages_per_city: int
    details_included: bool

    @property
    def scope_key(self) -> tuple[str, tuple[str, ...], int, bool]:
        return (
            self.search_keyword,
            tuple(sorted(self.cities)),
            self.pages_per_city,
            self.details_included,
        )


@dataclass(frozen=True)
class ReportDelivery:
    snapshot_id: int
    status: str
    text_message_id: int | None
    photo_message_id: int | None
    text_attempts: int
    photo_attempts: int
    last_error_type: str | None
