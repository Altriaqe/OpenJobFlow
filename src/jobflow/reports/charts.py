"""图表渲染层：把日报聚合指标绘制为可发送的 PNG，不读取原始岗位。"""

from collections.abc import Sequence
from io import BytesIO

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from jobflow.models.snapshot import KeywordTrend, NamedMetric

_COLORS = ("#2563EB", "#7C3AED", "#059669", "#D97706", "#DC2626", "#0891B2")
_FONT_CANDIDATES = ("Noto Sans CJK SC", "Microsoft YaHei", "SimHei", "DejaVu Sans")


def _select_font_family() -> str:
    installed = {font.name for font in font_manager.fontManager.ttflist}
    return next((name for name in _FONT_CANDIDATES if name in installed), "DejaVu Sans")


def _city_values(city_metrics: Sequence[NamedMetric]) -> tuple[list[str], list[int]]:
    labels = [metric.name for metric in city_metrics]
    if not labels:
        raise ValueError("city total must be positive")
    if len(labels) != len(set(labels)):
        raise ValueError("city names must be unique")

    values: list[int] = []
    for metric in city_metrics:
        value = metric.change.current
        if value is None:
            values.append(0)
        elif not isinstance(value, int):
            raise ValueError("city counts must be integers")
        elif value < 0:
            raise ValueError("city counts must not be negative")
        else:
            values.append(value)
    if sum(values) <= 0:
        raise ValueError("city total must be positive")
    return labels, values


def build_city_share_png(city_metrics: Sequence[NamedMetric]) -> bytes:
    """在内存中生成可直接上传 Telegram 的正方形城市占比 PNG。"""

    labels, values = _city_values(city_metrics)
    legend_labels = [f"{label}：{value} 个" for label, value in zip(labels, values, strict=True)]

    with matplotlib.rc_context({"font.family": _select_font_family(), "axes.unicode_minus": False}):
        fig, ax = plt.subplots(figsize=(8, 8), dpi=150)
        try:
            wedges, _, _ = ax.pie(
                values,
                labels=labels,
                autopct="%1.1f%%",
                startangle=90,
                colors=_COLORS[: len(values)],
            )
            ax.legend(
                wedges,
                legend_labels,
                loc="lower center",
                bbox_to_anchor=(0.5, -0.08),
                ncol=2,
            )
            ax.set_title("AI Agent 当日城市岗位占比")
            ax.axis("equal")
            output = BytesIO()
            fig.savefig(output, format="png", bbox_inches="tight", facecolor="white")
            return output.getvalue()
        finally:
            plt.close(fig)


def _keyword_city_matrix(
    trends: Sequence[KeywordTrend],
    cities: Sequence[str],
) -> tuple[list[str], list[str], list[list[int]]]:
    city_labels = list(cities)
    if not city_labels or len(city_labels) != len(set(city_labels)):
        raise ValueError("cities must be non-empty and unique")

    keyword_labels: list[str] = []
    matrix: list[list[int]] = []
    for trend in trends:
        if trend.new_by_city is None:
            raise ValueError("heatmap requires complete baseline")
        by_city = {metric.name: metric.count for metric in trend.new_by_city}
        if len(by_city) != len(trend.new_by_city):
            raise ValueError("trend city names must be unique")
        if set(by_city) != set(city_labels):
            raise ValueError("trend cities do not match report cities")
        keyword_labels.append(trend.keyword)
        matrix.append([by_city[city] for city in city_labels])

    if not keyword_labels or len(keyword_labels) != len(set(keyword_labels)):
        raise ValueError("keywords must be non-empty and unique")
    return keyword_labels, city_labels, matrix


def build_keyword_city_heatmap_png(
    trends: Sequence[KeywordTrend],
    *,
    cities: Sequence[str],
) -> bytes:
    """生成关键词与城市新增岗位数量热力图。"""

    keyword_labels, city_labels, matrix = _keyword_city_matrix(trends, cities)
    max_value = max(max(row) for row in matrix)

    with matplotlib.rc_context({"font.family": _select_font_family(), "axes.unicode_minus": False}):
        fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
        try:
            heatmap = ax.imshow(matrix, cmap="Blues", aspect="auto", vmin=0)
            ax.set_xticks(range(len(city_labels)), labels=city_labels)
            ax.set_yticks(range(len(keyword_labels)), labels=keyword_labels)
            ax.set_title("多岗位城市新增趋势", pad=16)
            for row_index, row in enumerate(matrix):
                for column_index, value in enumerate(row):
                    color = "white" if max_value > 0 and value > max_value / 2 else "#111827"
                    ax.text(
                        column_index,
                        row_index,
                        str(value),
                        ha="center",
                        va="center",
                        color=color,
                        fontsize=12,
                    )
            colorbar = fig.colorbar(heatmap, ax=ax, shrink=0.8)
            colorbar.set_label("新增岗位数")
            fig.text(
                0.5,
                0.02,
                "固定范围抓取样本，不代表全市场总量",
                ha="center",
                color="#4B5563",
            )
            fig.tight_layout(rect=(0, 0.05, 1, 1))
            output = BytesIO()
            fig.savefig(output, format="png", bbox_inches="tight", facecolor="white")
            return output.getvalue()
        finally:
            plt.close(fig)


def build_baseline_pending_png() -> bytes:
    """生成不包含虚构趋势数字的首日基线提示图。"""

    with matplotlib.rc_context({"font.family": _select_font_family(), "axes.unicode_minus": False}):
        fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
        try:
            ax.axis("off")
            ax.text(
                0.5,
                0.58,
                "趋势基线建立中",
                ha="center",
                va="center",
                fontsize=24,
                fontweight="bold",
                color="#1D4ED8",
                transform=ax.transAxes,
            )
            ax.text(
                0.5,
                0.43,
                "完成下一自然日采集后生成热力图",
                ha="center",
                va="center",
                fontsize=14,
                color="#4B5563",
                transform=ax.transAxes,
            )
            ax.text(
                0.5,
                0.30,
                "固定范围抓取样本，不代表全市场总量",
                ha="center",
                va="center",
                fontsize=11,
                color="#6B7280",
                transform=ax.transAxes,
            )
            output = BytesIO()
            fig.savefig(output, format="png", bbox_inches="tight", facecolor="white")
            return output.getvalue()
        finally:
            plt.close(fig)


def build_daily_new_jobs_cover_png() -> bytes:
    """生成固定 900×383 的公众号文章横向封面。"""
    with matplotlib.rc_context({"font.family": _select_font_family(), "axes.unicode_minus": False}):
        fig = plt.figure(figsize=(6, 383 / 150), dpi=150, facecolor="#1738C8")
        try:
            ax = fig.add_axes((0, 0, 1, 1))
            ax.set_facecolor("#1738C8")
            ax.axis("off")
            ax.text(
                0.08,
                0.82,
                "OPENJOBFLOW",
                color="#DCE6FF",
                fontsize=10,
                fontweight="bold",
            )
            ax.text(
                0.5,
                0.48,
                "今日新增岗位",
                ha="center",
                va="center",
                color="white",
                fontsize=28,
                fontweight="bold",
            )
            output = BytesIO()
            fig.savefig(output, format="png", dpi=150, bbox_inches=None, pad_inches=0)
            return output.getvalue()
        finally:
            plt.close(fig)
