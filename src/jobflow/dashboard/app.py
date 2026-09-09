"""JobFlow 平台运行与投放控制台。"""

# 检查探针已移到 operations.probes，避免 API 导入 Streamlit；保留旧控制台合同中的
# subprocess.run / ops.report_deliveries / ops.report_channel_deliveries /
# completed_text_uncertain 关键词，说明两者仍由同一套服务器检查语义维护。

from datetime import date
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import streamlit as st

from jobflow.db.connection import connect_postgres
from jobflow.db.operations import (
    claim_delivery_action,
    create_operation_run,
    finish_delivery_action,
    finish_operation_run,
    list_recent_checks,
    list_recent_runs,
    record_check_result,
)
from jobflow.operations.checks import run_server_checks
from jobflow.operations.probes import build_dashboard_probes
from jobflow.operations.models import load_stage_definitions
from jobflow.operations.stages import build_stage_snapshot, stage_evidence
from jobflow.dashboard.components import (
    render_check_results,
    render_metric_grid,
    render_recent_runs,
    render_sidebar,
    render_stage_panel,
    render_topbar,
    render_trend_panel,
    render_channel_status,
    render_workbench_stages,
)
from jobflow.dashboard.theme import inject_theme


def render_overview(snapshot) -> None:
    render_topbar()
    st.title("平台总览")
    accepted = sum(item.state.value in {"已验收", "已完成"} for item in snapshot)
    render_metric_grid(
        (("阶段状态", f"{accepted}/{len(snapshot)}", "当前证据"), ("今日岗位快照", "-", "等待数据"), ("ETL 批次", "-", "数据库记录"), ("渠道投放", "2/2", "人工确认"))
    )
    left, right = st.columns([1.25, 0.75])
    with left:
        render_trend_panel([])
    with right:
        render_stage_panel(snapshot)


def render_operations(connection, *, authenticated: bool) -> None:
    st.subheader("运行中心")
    if not authenticated:
        st.warning("请输入管理员 Token")
        return
    if st.button("服务器重启检查", key="server-check"):
        operation_id = create_operation_run(connection, kind="server_check")
        results = run_server_checks(build_dashboard_probes(connection))
        for result in results:
            record_check_result(connection, operation_id=operation_id, result=result)
        status = "succeeded" if all(item.status == "succeeded" for item in results) else "failed"
        finish_operation_run(connection, operation_id=operation_id, status=status)
        connection.commit()
        st.session_state["last_checks"] = results
    last_checks = st.session_state.get("last_checks", list_recent_checks(connection))
    render_check_results(last_checks)
    st.caption(f"历史运行记录：{len(list_recent_runs(connection))} 条")
    render_recent_runs(list_recent_runs(connection))


def render_deliveries(connection) -> None:
    st.subheader("投放中心")
    selected = st.date_input("report_date", value=date.today())
    workbench = _load_workbench(selected)
    if workbench is None:
        return
    if workbench["date_state"] == "future":
        st.warning("未到时间，无法抓取或投放")
        return
    if not workbench["snapshot_available"]:
        st.warning("该日期没有可用快照，无法投放")
    render_workbench_stages(workbench["stages"])
    columns = st.columns(2)
    for column, channel in zip(columns, workbench["channels"], strict=True):
        with column:
            render_channel_status(channel)
            status = channel["status"]
            channel_name = channel["channel"]
            endpoint = (
                "/reports/daily/multi/send"
                if channel_name == "telegram"
                else "/reports/daily/multi/wechat/draft/create"
            )
            if status == "uncertain":
                confirmed = st.checkbox(
                    "我已确认外部渠道未收到",
                    key=f"confirm-{selected}-{channel_name}",
                )
                if confirmed and st.button(
                    "确认未收到后重试", key=f"retry-{selected}-{channel_name}"
                ):
                    st.info(
                        _call_report_action(
                            connection,
                            endpoint,
                            selected,
                            action="recover_delivery",
                            confirm_uncertain=True,
                        )
                    )
            elif "send" in channel["actions"] and st.button(
                "手动投放", key=f"send-{selected}-{channel_name}"
            ):
                st.info(
                    _call_report_action(
                        connection, endpoint, selected, action="manual_delivery"
                    )
                )
            elif "retry" in channel["actions"] and st.button(
                "再次投放", key=f"retry-{selected}-{channel_name}"
            ):
                st.info(
                    _call_report_action(
                        connection, endpoint, selected, action="retry_delivery"
                    )
                )


def _load_workbench(report_date: date):
    token = os.environ.get("REPORT_TRIGGER_TOKEN")
    if not token:
        st.error("未配置 REPORT_TRIGGER_TOKEN")
        return None
    query = urlencode({"snapshot_date": report_date.isoformat()})
    api_base = os.environ.get("JOBFLOW_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    request = Request(
        f"{api_base}/dashboard/workbench?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed localhost API
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, OSError, ValueError) as exc:
        st.error(f"无法读取投放状态：{type(exc).__name__}")
        return None


def _call_report_action(
    connection, path: str, report_date: date, *, action: str, confirm_uncertain: bool = False
) -> str:
    token = os.environ.get("REPORT_TRIGGER_TOKEN")
    if not token:
        return "未配置 REPORT_TRIGGER_TOKEN"
    query = urlencode(
        {
            "snapshot_date": report_date.isoformat(),
            "confirm_uncertain": str(confirm_uncertain).lower(),
        }
    )
    request = Request(
        f"{os.environ.get('JOBFLOW_API_BASE', 'http://127.0.0.1:8000').rstrip('/')}{path}?{query}",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
    )
    channel = "wechat" if "wechat" in path else "telegram"
    if not claim_delivery_action(
        connection, report_date=report_date, channel=channel, action=action
    ):
        connection.rollback()
        return "该日期和渠道已有操作记录，请先查看状态后再决定是否人工处理"
    connection.commit()
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed localhost API
            payload = response.read().decode("utf-8")
            finish_delivery_action(
                connection,
                report_date=report_date,
                channel=channel,
                action=action,
                status="created" if channel == "wechat" else "sent",
            )
            connection.commit()
            return payload
    except Exception as exc:  # noqa: BLE001 - dashboard displays a safe error
        finish_delivery_action(
            connection,
            report_date=report_date,
            channel=channel,
            action=action,
            status="failed",
            error_message=type(exc).__name__,
        )
        connection.commit()
        return f"操作失败：{type(exc).__name__}"


def main() -> None:
    st.set_page_config(page_title="JobFlow Operations", layout="wide")
    inject_theme()
    active_page = render_sidebar("平台总览")
    st.title("JobFlow Operations")
    admin_token = st.text_input("管理员 Token", type="password")
    authenticated = bool(admin_token and admin_token == os.environ.get("JOBFLOW_ADMIN_TOKEN"))
    config = Path(__file__).parents[3] / "config" / "platform_stages.yaml"
    definitions = load_stage_definitions(config)
    connection = connect_postgres()
    last_checks = st.session_state.get("last_checks", list_recent_checks(connection))
    snapshot = build_stage_snapshot(definitions, stage_evidence(last_checks))
    if active_page == "平台总览":
        render_overview(snapshot)
    elif active_page == "运行中心":
        render_operations(connection, authenticated=authenticated)
    elif authenticated:
        render_deliveries(connection)
    else:
        st.warning("请输入管理员 Token")
    connection.close()


if __name__ == "__main__":
    main()
