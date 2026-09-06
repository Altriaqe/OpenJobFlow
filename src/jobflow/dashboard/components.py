"""Dashboard 纯展示组件；不执行 SQL，不读取秘密配置。"""

from collections.abc import Sequence

import streamlit as st

from jobflow.operations.models import CheckResult, StageSnapshot


def render_sidebar(active_page: str) -> None:
    with st.sidebar:
        st.markdown("## JobFlow")
        st.caption("Operations")
        for item in ("平台总览", "运行中心", "投放中心", "分析指标", "告警记录"):
            st.markdown(f"{'▸ ' if item == active_page else ''}{item}")


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
    st.markdown('<div class="jf-panel">', unsafe_allow_html=True)
    st.markdown("**阶段状态**")
    for item in snapshot:
        state = item.state.value
        css = "observe" if state == "观察中" else "error" if state == "异常" else ""
        st.markdown(
            f'<div class="jf-row">{item.definition.name}<span style="float:right" class="jf-status {css}">{state}</span></div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)


def render_trend_panel(values: Sequence[int]) -> None:
    st.markdown('<div class="jf-panel">', unsafe_allow_html=True)
    st.markdown("**每日采集量**")
    st.bar_chart({"岗位快照": list(values)}, height=220)
    st.markdown('</div>', unsafe_allow_html=True)


def render_recent_runs(runs) -> None:
    st.markdown('<div class="jf-panel">', unsafe_allow_html=True)
    st.markdown("**最近运行**")
    for run in runs[:5]:
        operation_id, kind, report_date, status, error_message, started_at, finished_at = run
        del operation_id, error_message
        label = "服务器重启检查" if kind == "server_check" else "恢复运行"
        st.markdown(
            f'<div class="jf-row">{label}　{report_date or "-"}　<span class="jf-status">{status}</span></div>',
            unsafe_allow_html=True,
        )
        del started_at, finished_at
    st.markdown('</div>', unsafe_allow_html=True)


def render_check_results(results: Sequence[CheckResult]) -> None:
    for result in results:
        css = "" if result.status == "succeeded" else "error"
        st.markdown(
            f'<div class="jf-row">{result.name}<span style="float:right" class="jf-status {css}">{result.status}</span><br><small>{result.summary}</small></div>',
            unsafe_allow_html=True,
        )
