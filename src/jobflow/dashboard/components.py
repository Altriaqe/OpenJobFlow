"""Dashboard 纯展示组件；不执行 SQL，不读取秘密配置。"""

from collections.abc import Sequence

import streamlit as st

from jobflow.operations.models import CheckResult, StageSnapshot


def render_sidebar(active_page: str) -> str:
    with st.sidebar:
        st.markdown("## JobFlow")
        st.caption("Operations")
        available = ("平台总览", "运行中心", "投放中心")
        selected = st.radio(
            "导航",
            available,
            index=available.index(active_page) if active_page in available else 0,
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.caption("规划中")
        st.markdown("分析指标")
        st.markdown("告警记录")
    return selected


def render_topbar() -> None:
    left, right = st.columns([2, 1])
    with left:
        st.caption("JobFlow / Operations / Overview")
    with right:
        st.caption("最近 24 小时　　自动刷新：手动")


def render_metric_grid(metrics: Sequence[tuple[str, str, str]]) -> None:
    columns = st.columns(len(metrics))
    for column, (label, value, detail) in zip(columns, metrics, strict=True):
        with column:
            st.metric(label, value, detail)


def render_stage_panel(snapshot: Sequence[StageSnapshot]) -> None:
    with st.container(border=True):
        st.markdown("**阶段状态**")
        for item in snapshot:
            state = item.state.value
            css = "observe" if state == "观察中" else "error" if state == "异常" else ""
            st.markdown(
                f'<div class="jf-row">{item.definition.name}<span style="float:right" class="jf-status {css}">{state}</span></div>',
                unsafe_allow_html=True,
            )


def render_trend_panel(values: Sequence[int]) -> None:
    with st.container(border=True):
        st.markdown("**每日采集量**")
        if values:
            st.bar_chart({"岗位快照": list(values)}, height=220)
        else:
            st.info("暂无趋势数据")


def render_workbench_stages(stages) -> None:
    with st.container(border=True):
        st.markdown("**每日链路**")
        labels = {"snapshot": "抓取与快照", "article": "文章包"}
        for stage in stages:
            status = "已就绪" if stage["status"] == "ready" else "未准备"
            css = "" if stage["status"] == "ready" else "error"
            st.markdown(
                f'<div class="jf-row">{labels.get(stage["id"], stage["id"])}'
                f'<span style="float:right" class="jf-status {css}">{status}</span></div>',
                unsafe_allow_html=True,
            )


def render_channel_status(channel: dict[str, object]) -> None:
    labels = {"telegram": "Telegram", "wechat": "微信公众号草稿"}
    status_labels = {
        "not_sent": "未投放",
        "pending": "未投放",
        "sending": "投放中",
        "creating": "创建中",
        "sent": "已投放",
        "created": "草稿已创建",
        "failed": "明确失败",
        "uncertain": "结果不确定",
    }
    status = channel.get("status", "unknown")
    css = "error" if status in {"failed", "uncertain"} else ""
    st.markdown(
        f'<div class="jf-row"><strong>{labels.get(channel["channel"], channel["channel"])}</strong>'
        f'<span style="float:right" class="jf-status {css}">'
        f'{status_labels.get(status, status)}</span></div>',
        unsafe_allow_html=True,
    )
    if channel.get("error_code"):
        st.caption(f"错误码：{channel['error_code']}")


def render_recent_runs(runs) -> None:
    with st.container(border=True):
        st.markdown("**最近运行**")
        for run in runs[:5]:
            operation_id, kind, report_date, status, error_message, started_at, finished_at = run
            del operation_id, error_message, started_at, finished_at
            label = "服务器重启检查" if kind == "server_check" else "恢复运行"
            st.markdown(
                f'<div class="jf-row">{label}　{report_date or "-"}　<span class="jf-status">{status}</span></div>',
                unsafe_allow_html=True,
            )


def render_check_results(results: Sequence[CheckResult]) -> None:
    for result in results:
        css = "" if result.status == "succeeded" else "error"
        st.markdown(
            f'<div class="jf-row">{result.name}<span style="float:right" class="jf-status {css}">{result.status}</span><br><small>{result.summary}</small></div>',
            unsafe_allow_html=True,
        )
