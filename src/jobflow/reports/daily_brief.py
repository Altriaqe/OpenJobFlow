"""日报文字渲染层：把聚合指标格式化为受长度约束的中文简报。"""

from datetime import date
from decimal import Decimal

from jobflow.models.snapshot import (
    DailyComparison,
    KeywordTrend,
    MetricChange,
    NamedMetric,
    WeeklyComparison,
)

TELEGRAM_MESSAGE_LIMIT = 4096

_WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def _number(value: int | Decimal | None) -> str:
    if value is None:
        return "暂无"
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return str(value)


def _format_direction(change: MetricChange, *, unit: str = "个") -> str:
    if change.previous is None or change.delta is None:
        return "暂无历史基准"
    if change.delta == 0:
        return "持平"
    arrow = "↑" if change.delta > 0 else "↓"
    amount = abs(change.delta)
    if change.percent is None:
        return f"{arrow} {_number(amount)}{unit}（比例不适用）"
    return f"{arrow} {_number(amount)}{unit}（{arrow} {abs(change.percent):.1f}%）"


def _format_salary(change: MetricChange) -> str:
    if change.current is None:
        return "暂无有效月薪样本"
    return f"{_number(change.current)}K/月｜{_format_direction(change, unit='K')}"


def _top_current(metrics: tuple[NamedMetric, ...]) -> NamedMetric | None:
    available = [metric for metric in metrics if metric.change.current is not None]
    return max(available, key=lambda metric: (metric.change.current, metric.name), default=None)


def _management_summary(daily: DailyComparison) -> list[str]:
    total = daily.total
    if not daily.has_baseline:
        total_fact = f"今日采集到 {_number(total.current)} 个去重岗位，暂无同口径历史基准。"
    elif total.delta == 0:
        total_fact = "岗位总量较前一自然日持平。"
    else:
        total_fact = f"岗位总量较前一自然日{_format_direction(total)}。"

    positive_cities = [
        metric
        for metric in daily.city_metrics
        if metric.change.delta is not None and metric.change.delta > 0
    ]
    if positive_cities:
        city = max(positive_cities, key=lambda metric: (metric.change.delta, metric.name))
        city_fact = f"{city.name}岗位增量最明显，{_format_direction(city.change)}。"
    else:
        city = _top_current(daily.city_metrics)
        city_fact = (
            "当前快照暂无城市岗位数据。"
            if city is None
            else f"当前岗位数最多的城市是{city.name}，共 {_number(city.change.current)} 个。"
        )

    skill = _top_current(daily.skills)
    skill_fact = (
        "当前快照暂无技能标签。"
        if skill is None
        else f"覆盖岗位最多的技能是 {skill.name}，涉及 {_number(skill.change.current)} 个岗位。"
    )
    return [f"• {total_fact}", f"• {city_fact}", f"• {skill_fact}"]


def _metric_lines(metrics: tuple[NamedMetric, ...], *, numbered: bool = False) -> list[str]:
    lines = []
    for index, metric in enumerate(metrics, start=1):
        prefix = f"{index}." if numbered else "•"
        lines.append(
            f"{prefix} {metric.name}：{_number(metric.change.current)}｜"
            f"{_format_direction(metric.change)}"
        )
    return lines


def _weekly_lines(weekly: WeeklyComparison) -> list[str]:
    start, end = weekly.current_range
    lines = [
        f"【本周趋势｜{start.isoformat()} 至 {end.isoformat()}】",
        f"本周去重岗位：{_number(weekly.total.current)} 个",
        f"较上一完整周：{_format_direction(weekly.total)}",
        "",
        "【周度城市变化】",
        *_metric_lines(weekly.city_metrics),
        "",
        "【周度技能变化】",
        *(_metric_lines(weekly.skills) or ["• 暂无技能标签"]),
        "",
        "【周度薪资】",
        f"月薪中位数：{_format_salary(weekly.salary_midpoint_median)}",
        "",
        "【周度观察】",
        f"• 本周岗位总量较上一完整周{_format_direction(weekly.total)}。",
    ]
    positive_cities = [
        metric
        for metric in weekly.city_metrics
        if metric.change.delta is not None and metric.change.delta > 0
    ]
    if positive_cities:
        city = max(positive_cities, key=lambda metric: (metric.change.delta, metric.name))
        lines.append(f"• 周岗位增量最明显的城市是{city.name}，{_format_direction(city.change)}。")
    else:
        lines.append("• 本周没有城市出现正向岗位增量。")
    lines.extend(
        [
            "",
            "说明：周岗位按来源与岗位 ID 去重；",
            "仅比较两个完整的周一至周日周期。",
            "",
        ]
    )
    return lines


def _validate_length(report: str) -> str:
    if len(report) > TELEGRAM_MESSAGE_LIMIT:
        raise ValueError("daily brief exceeds Telegram message limit")
    return report


def _top_new_cities(trend: KeywordTrend) -> tuple[tuple[str, ...], int] | None:
    if trend.new_by_city is None:
        return None
    top_count = max((metric.count for metric in trend.new_by_city), default=0)
    leaders = tuple(metric.name for metric in trend.new_by_city if metric.count == top_count)
    return leaders, top_count


def build_multi_keyword_brief(
    *,
    report_date: date,
    trends: tuple[KeywordTrend, ...],
    city_count: int,
    pages_per_city: int,
) -> str:
    """生成一条多关键词固定样本趋势简报。"""

    if not trends or len({trend.keyword for trend in trends}) != len(trends):
        raise ValueError("trends must contain unique keywords")
    if city_count <= 0 or pages_per_city <= 0:
        raise ValueError("snapshot scope must be positive")

    has_complete_baseline = all(trend.new_by_city is not None for trend in trends)
    lines = [
        "━━━━━━━━━━━━━━━━━━",
        "JobFlow｜多岗位招聘趋势日报",
        f"{report_date.isoformat()}　{_WEEKDAYS[report_date.weekday()]}",
        "━━━━━━━━━━━━━━━━━━",
        "",
        "【岗位趋势】",
    ]
    if not has_complete_baseline:
        lines.append("趋势基线建立中，完成下一自然日采集后生成增减趋势。")
    else:
        for trend in trends:
            leader = _top_new_cities(trend)
            if leader is None or trend.daily.new_count is None:
                raise ValueError("complete baseline requires new job counts")
            city_names, new_count = leader
            if new_count == 0:
                city_summary = "各城市均无新增样本"
            else:
                tie = "（并列）" if len(city_names) > 1 else ""
                city_summary = f"新增最多城市：{'、'.join(city_names)}{tie}（{new_count} 个）"
            lines.append(
                f"• {trend.keyword}：较昨日新增采集 {trend.daily.new_count} 个；{city_summary}"
            )

    lines.extend(["", "【城市优势】"])
    if not has_complete_baseline:
        lines.append("• 暂无完整前日基线。")
    else:
        city_names = tuple(metric.name for metric in trends[0].new_by_city or ())
        for city in city_names:
            values = [
                (
                    trend.keyword,
                    next(metric.count for metric in trend.new_by_city or () if metric.name == city),
                )
                for trend in trends
            ]
            best = max(value for _, value in values)
            if best == 0:
                lines.append(f"• {city}：今日暂无新增样本")
            else:
                leaders = tuple(keyword for keyword, value in values if value == best)
                tie = "（并列）" if len(leaders) > 1 else ""
                lines.append(f"• {city}：{'、'.join(leaders)}{tie}新增样本最多（{best} 个）")

    if report_date.weekday() == 6:
        lines.extend(["", "【周趋势】"])
        if all(trend.weekly is not None for trend in trends):
            for trend in trends:
                if trend.weekly is None:
                    raise ValueError("weekly comparison is required")
                lines.append(f"• {trend.keyword}：{_format_direction(trend.weekly.total)}")
        else:
            lines.append("• 周趋势数据不足。")

    lines.extend(
        [
            "",
            "【数据口径】",
            f"{len(trends)} 个关键词 × {city_count} 个城市 × 每组 {pages_per_city} 页",
            "数据表示固定范围抓取样本，不代表全市场总量。",
            "同一岗位可能被多个关键词命中。",
            "",
            "JobFlow｜每日招聘数据快照",
        ]
    )
    return _validate_length("\n".join(lines))


def build_daily_brief(
    *,
    report_date: date,
    keyword: str,
    city_count: int,
    pages_per_city: int,
    daily: DailyComparison,
    weekly: WeeklyComparison | None = None,
) -> str:
    """生成不依赖 Markdown 或大模型的确定性中文招聘简报。"""

    snapshot_values = (
        (str(daily.new_count), str(daily.continued_count), str(daily.missing_count))
        if daily.has_baseline
        else ("暂无历史基准", "暂无历史基准", "暂无历史基准")
    )
    lines = [
        "━━━━━━━━━━━━━━━━━━",
        f"JobFlow｜{keyword} 招聘市场日报",
        f"{report_date.isoformat()}　{_WEEKDAYS[report_date.weekday()]}",
        "━━━━━━━━━━━━━━━━━━",
        "",
        "【今日概览】",
        f"岗位总量：{_number(daily.total.current)} 个",
        f"日环比：{_format_direction(daily.total)}",
        f"月薪中位数：{_format_salary(daily.salary_midpoint_median)}",
        "",
        "【管理摘要】",
        *_management_summary(daily),
        "",
        "【城市表现】",
        *_metric_lines(daily.city_metrics),
        "",
        "【岗位快照变化】",
        f"新增采集：{snapshot_values[0]}" + (" 个" if daily.has_baseline else ""),
        f"连续出现：{snapshot_values[1]}" + (" 个" if daily.has_baseline else ""),
        f"本次未出现：{snapshot_values[2]}" + (" 个" if daily.has_baseline else ""),
        "",
        "【热门技能】",
        *(_metric_lines(daily.skills, numbered=True) or ["暂无技能标签"]),
        "",
    ]
    if weekly is not None and report_date.weekday() == 6:
        lines.extend(_weekly_lines(weekly))
    lines.extend(
        [
            "【数据口径】",
            f"关键词：{keyword}",
            f"范围：{city_count} 城市 × 每城 {pages_per_city} 页",
            "说明：本次未出现不代表岗位已经下线。",
            "",
            "JobFlow｜每日招聘数据快照",
        ]
    )
    return _validate_length("\n".join(lines))
