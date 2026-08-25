from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from jobflow.models.snapshot import SnapshotMetadata


def test_snapshot_metadata_exposes_scope_and_city_count() -> None:
    metadata = SnapshotMetadata(
        snapshot_date=date(2026, 8, 18),
        search_keyword=" AI Agent ",
        cities=(" 上海 ", "北京", "杭州", "深圳"),
        pages_per_city=3,
        details_included=False,
    )

    assert metadata.search_keyword == "AI Agent"
    assert metadata.cities == ("上海", "北京", "杭州", "深圳")
    assert metadata.city_count == 4
    assert metadata.scope_key == (
        "AI Agent",
        ("上海", "北京", "杭州", "深圳"),
        3,
        False,
    )


def test_snapshot_scope_does_not_depend_on_city_order() -> None:
    first = SnapshotMetadata(
        snapshot_date=date(2026, 8, 18),
        search_keyword="AI Agent",
        cities=("上海", "北京", "杭州", "深圳"),
        pages_per_city=3,
        details_included=False,
    )
    second = SnapshotMetadata(
        snapshot_date=date(2026, 8, 19),
        search_keyword="AI Agent",
        cities=("深圳", "杭州", "北京", "上海"),
        pages_per_city=3,
        details_included=False,
    )

    assert first.scope_key == second.scope_key


@pytest.mark.parametrize(
    ("keyword", "cities", "pages", "message"),
    [
        ("", ("上海",), 3, "search_keyword"),
        ("AI Agent", (), 3, "cities"),
        ("AI Agent", ("上海", " "), 3, "cities"),
        ("AI Agent", ("上海", "上海"), 3, "unique"),
        ("AI Agent", ("上海",), 0, "pages_per_city"),
    ],
)
def test_snapshot_metadata_rejects_invalid_scope(
    keyword: str,
    cities: tuple[str, ...],
    pages: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        SnapshotMetadata(
            snapshot_date=date(2026, 8, 18),
            search_keyword=keyword,
            cities=cities,
            pages_per_city=pages,
            details_included=False,
        )


def test_snapshot_metadata_is_immutable() -> None:
    metadata = SnapshotMetadata(
        snapshot_date=date(2026, 8, 18),
        search_keyword="AI Agent",
        cities=("上海", "北京", "杭州", "深圳"),
        pages_per_city=3,
        details_included=False,
    )

    with pytest.raises(FrozenInstanceError):
        metadata.pages_per_city = 5
