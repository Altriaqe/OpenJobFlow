from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from jobflow.models.snapshot import (
    DailyComparison,
    KeywordTrend,
    MetricChange,
    NamedCount,
    NamedMetric,
)
from jobflow.reports.charts import (
    _keyword_city_matrix,
    build_baseline_pending_png,
    build_city_share_png,
    build_daily_new_jobs_cover_png,
    build_keyword_city_heatmap_png,
)


def png_dimensions(image: bytes) -> tuple[int, int]:
    return int.from_bytes(image[16:20], "big"), int.from_bytes(image[20:24], "big")


def city_metrics(values: tuple[int, ...] = (82, 76, 63, 65)) -> tuple[NamedMetric, ...]:
    names = ("上海", "北京", "杭州", "深圳")
    return tuple(
        NamedMetric(name, MetricChange(value, value - 1, 1, Decimal("1.0")))
        for name, value in zip(names, values, strict=True)
    )


def keyword_trends(*, has_baseline: bool = True) -> tuple[KeywordTrend, ...]:
    keywords = ("AI Agent", "Python开发", "Java开发", "数据分析")
    rows = ((5, 2, 1, 0), (1, 2, 3, 6), (2, 5, 1, 4), (3, 2, 7, 1))
    daily = DailyComparison(
        has_baseline=has_baseline,
        total=MetricChange(12, 10 if has_baseline else None, 2 if has_baseline else None, None),
        city_metrics=city_metrics((3, 3, 3, 3)),
        new_count=8 if has_baseline else None,
        continued_count=4 if has_baseline else None,
        missing_count=2 if has_baseline else None,
        skills=(),
        salary_midpoint_median=MetricChange(None, None, None, None),
    )
    return tuple(
        KeywordTrend(
            keyword,
            daily,
            (
                tuple(
                    NamedCount(city, count)
                    for city, count in zip(("上海", "北京", "杭州", "深圳"), row, strict=True)
                )
                if has_baseline
                else None
            ),
        )
        for keyword, row in zip(keywords, rows, strict=True)
    )


def test_build_city_share_png_returns_valid_png() -> None:
    image = build_city_share_png(city_metrics())

    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(image) > 10_000


@pytest.mark.parametrize(
    ("metrics", "message"),
    [
        (city_metrics((0, 0, 0, 0)), "positive"),
        (city_metrics((1, -1, 1, 1)), "negative"),
        (
            (
                NamedMetric("上海", MetricChange(1, 1, 0, Decimal("0.0"))),
                NamedMetric("上海", MetricChange(2, 1, 1, Decimal("100.0"))),
            ),
            "unique",
        ),
    ],
)
def test_build_city_share_png_rejects_invalid_counts(metrics, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build_city_share_png(metrics)


def test_chart_passes_exact_city_values_to_pie_and_legend() -> None:
    figure = Mock()
    axes = Mock()
    wedges = [Mock(), Mock(), Mock(), Mock()]
    axes.pie.return_value = (wedges, [], [])

    def savefig(output, **_kwargs) -> None:
        output.write(b"\x89PNG\r\n\x1a\n")

    figure.savefig.side_effect = savefig
    with patch("jobflow.reports.charts.plt.subplots", return_value=(figure, axes)):
        build_city_share_png(city_metrics())

    assert axes.pie.call_args.args[0] == [82, 76, 63, 65]
    assert axes.pie.call_args.kwargs["labels"] == ["上海", "北京", "杭州", "深圳"]
    assert axes.legend.call_args.args[1] == [
        "上海：82 个",
        "北京：76 个",
        "杭州：63 个",
        "深圳：65 个",
    ]


def test_keyword_city_matrix_preserves_keyword_and_city_order() -> None:
    keywords, cities, matrix = _keyword_city_matrix(
        keyword_trends(),
        ("上海", "北京", "杭州", "深圳"),
    )

    assert keywords == ["AI Agent", "Python开发", "Java开发", "数据分析"]
    assert cities == ["上海", "北京", "杭州", "深圳"]
    assert matrix == [[5, 2, 1, 0], [1, 2, 3, 6], [2, 5, 1, 4], [3, 2, 7, 1]]


def test_build_keyword_city_heatmap_png_returns_valid_png() -> None:
    image = build_keyword_city_heatmap_png(
        keyword_trends(),
        cities=("上海", "北京", "杭州", "深圳"),
    )

    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(image) > 10_000


def test_build_keyword_city_heatmap_rejects_missing_baseline() -> None:
    with pytest.raises(ValueError, match="baseline"):
        build_keyword_city_heatmap_png(
            keyword_trends(has_baseline=False),
            cities=("上海", "北京", "杭州", "深圳"),
        )


def test_build_baseline_pending_png_returns_valid_png() -> None:
    image = build_baseline_pending_png()

    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(image) > 10_000


def test_daily_new_jobs_cover_is_landscape_png() -> None:
    image = build_daily_new_jobs_cover_png()

    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert png_dimensions(image) == (900, 383)
