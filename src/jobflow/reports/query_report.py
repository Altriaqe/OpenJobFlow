"""固定规则简报渲染器：不调用模型，只使用数据库聚合结果。"""

from __future__ import annotations

from datetime import datetime


def _normalise_rows(rows: list[dict[str, object]]) -> list[tuple[str, int]]:
    """Return validated city/count pairs in descending count order."""
    normalised: list[tuple[str, int]] = []
    for row in rows:
        city = str(row.get("city", "未知城市"))
        count = int(row.get("job_count", 0))
        normalised.append((city, count))
    return sorted(normalised, key=lambda item: (-item[1], item[0]))


def build_query_report_header(*, generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now()
    return "\n".join(
        [
            "━━━━━━━━━━━━━━━━━━━━",
            "JobFlow｜招聘市场数据简报",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            f"报告时间：{generated_at:%Y-%m-%d %H:%M}",
            "数据范围：当前数据库已入库职位",
            "统计维度：城市岗位数量",
            "数据状态：只读查询结果",
        ]
    )


def build_query_report_metrics(rows: list[tuple[str, int]]) -> str:
    total = sum(count for _, count in rows)
    city_count = len(rows)
    leader_city, leader_count = rows[0]
    top_three_share = (sum(count for _, count in rows[:3]) / total * 100) if total else 0
    return "\n".join(
        [
            "一、核心指标",
            f"• 覆盖城市：{city_count} 个",
            f"• 职位总量：{total} 个",
            f"• 最高城市岗位数：{leader_city}，{leader_count} 个",
            f"• 前三城市职位占比：{top_three_share:.1f}%",
        ]
    )


def _build_city_table(rows: list[tuple[str, int]]) -> str:
    total = sum(count for _, count in rows)
    lines = ["二、城市岗位分布", "排名  城市       岗位数     占比"]
    for index, (city, count) in enumerate(rows[:10], start=1):
        share = (count / total * 100) if total else 0
        lines.append(f"{index:02d}    {city:<8} {count:>6}     {share:>5.1f}%")
    return "\n".join(lines)


def build_query_report_observations(rows: list[tuple[str, int]]) -> str:
    total = sum(count for _, count in rows)
    top_three_share = (sum(count for _, count in rows[:3]) / total * 100) if total else 0
    leader_city, _ = rows[0]
    observations = [f"• {leader_city}岗位数量位居首位。"]
    if len(rows) > 1 and rows[0][1] > rows[-1][1]:
        observations.append("• 当前城市之间的岗位分布存在差异。")
    if top_three_share >= 60:
        observations.append("• 当前岗位主要集中在前 3 个城市。")
    return "\n".join(
        [
            "三、数据观察",
            *observations,
            "",
            "四、业务提示",
            "• 可优先关注岗位数量靠前的城市。",
            "• 如需判断增长趋势，还需要不同日期的历史快照。",
            "• 当前数据没有历史对比，因此无法判断趋势。",
            "• 当前结果适合用于招聘数据查询和区域分布观察。",
        ]
    )


def build_query_report(
    rows: list[dict[str, object]], *, generated_at: datetime | None = None
) -> str:
    """Build a deterministic Chinese report from read-only city metrics."""
    normalised = _normalise_rows(rows)
    if not normalised:
        return ""

    return "\n\n".join(
        [
            build_query_report_header(generated_at=generated_at),
            build_query_report_metrics(normalised),
            _build_city_table(normalised),
            build_query_report_observations(normalised),
            "\n".join(
                [
                    "五、口径说明",
                    "• 统计对象：当前数据库中的职位记录。",
                    "• 岗位数量按系统当前聚合结果计算。",
                    "• 本报告不代表完整招聘市场规模。",
                    "• 本报告未推断薪资、技能需求、增长趋势或因果关系。",
                    "",
                    "━━━━━━━━━━━━━━━━━━━━",
                    "JobFlow｜数据查询服务",
                    "━━━━━━━━━━━━━━━━━━━━",
                ]
            ),
        ]
    )
