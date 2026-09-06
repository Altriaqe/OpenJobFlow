"""JobFlow 平台运行与投放控制台。"""

from datetime import date
import os
from pathlib import Path
import subprocess
from urllib.parse import urlencode
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
from jobflow.operations.checks import database_probe, default_probes, run_server_checks
from jobflow.operations.models import StageEvidence, load_stage_definitions
from jobflow.operations.stages import build_stage_snapshot


def build_dashboard_probes(connection):
    probes = default_probes()
    probes.update(
        {
            "postgres": database_probe("postgres", connection, "SELECT TRUE"),
            "latest_etl": database_probe(
                "latest_etl",
                connection,
                "SELECT EXISTS (SELECT 1 FROM ops.batches WHERE status = 'succeeded')",
            ),
            "telegram": database_probe(
                "telegram",
                connection,
                """SELECT EXISTS (
                    SELECT 1 FROM ops.report_channel_deliveries
                    WHERE channel = 'telegram' AND status = 'sent'
                )""",
            ),
            "wechat": database_probe(
                "wechat",
                connection,
                """SELECT EXISTS (
                    SELECT 1 FROM ops.wechat_draft_jobs WHERE status = 'created'
                )""",
            ),
        }
    )
    boss_check = os.environ.get("JOBFLOW_BOSS_CHECK_COMMAND")
    if boss_check:
        probes["boss_login"] = lambda: _run_configured_check(boss_check)
    return probes


def _run_configured_check(command: str):
    result = subprocess.run(
        ["bash", "-lc", command], capture_output=True, text=True, timeout=30, check=False
    )
    from jobflow.operations.models import CheckResult

    return CheckResult(
        "boss_login",
        "succeeded" if result.returncode == 0 else "failed",
        "检查通过" if result.returncode == 0 else "命令返回失败",
        None if result.returncode == 0 else f"exit_{result.returncode}",
    )


def stage_evidence(last_checks):
    statuses = {item.name: item.status for item in last_checks}
    evidence = {
        stage_id: StageEvidence()
        for stage_id in (
            "data_source",
            "collection",
            "etl",
            "postgres",
            "analytics_api",
            "reports",
            "telegram",
            "wechat",
        )
    }
    infrastructure_ok = statuses.get("postgres") == "succeeded"
    evidence["data_source"] = StageEvidence(implemented=True)
    evidence["collection"] = StageEvidence(
        implemented=True, accepted=statuses.get("boss_login") == "succeeded"
    )
    evidence["etl"] = StageEvidence(
        implemented=True, accepted=statuses.get("latest_etl") == "succeeded"
    )
    evidence["postgres"] = StageEvidence(implemented=True, accepted=infrastructure_ok)
    evidence["analytics_api"] = StageEvidence(
        implemented=True, accepted=statuses.get("ready") == "succeeded"
    )
    evidence["reports"] = StageEvidence(
        implemented=True, accepted=statuses.get("latest_etl") == "succeeded"
    )
    evidence["telegram"] = StageEvidence(
        implemented=True, accepted=statuses.get("telegram") == "succeeded"
    )
    evidence["wechat"] = StageEvidence(
        implemented=True, accepted=statuses.get("wechat") == "succeeded"
    )
    return evidence


def render_overview(snapshot) -> None:
    st.subheader("平台总览")
    for item in snapshot:
        st.metric(item.definition.name, item.state.value)


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
    for result in last_checks:
        st.write(f"{result.name}: {result.status} - {result.summary}")
    st.caption(f"历史运行记录：{len(list_recent_runs(connection))} 条")
    checks_passed = bool(last_checks) and all(item.status == "succeeded" for item in last_checks)
    if st.button("手动恢复运行", key="recovery-run", disabled=not checks_passed):
        operation_id = create_operation_run(connection, kind="recovery_run")
        result = _run_recovery()
        finish_operation_run(
            connection,
            operation_id=operation_id,
            status="succeeded" if result.startswith("恢复运行已完成") else "failed",
            error_message=None if result.startswith("恢复运行已完成") else result,
        )
        connection.commit()
        st.info(result)


def render_deliveries(connection) -> None:
    st.subheader("投放中心")
    selected = st.date_input("report_date", value=date.today())
    if st.button("手动投放 Telegram", key="telegram-delivery", disabled=selected is None):
        st.info(_call_report_action(connection, "/reports/daily/multi/send", selected))
    if st.button("创建微信公众号草稿", key="wechat-delivery", disabled=selected is None):
        st.info(
            _call_report_action(connection, "/reports/daily/multi/wechat/draft/create", selected)
        )


def _call_report_action(connection, path: str, report_date: date) -> str:
    token = os.environ.get("REPORT_TRIGGER_TOKEN")
    if not token:
        return "未配置 REPORT_TRIGGER_TOKEN"
    query = urlencode({"snapshot_date": report_date.isoformat()})
    request = Request(
        f"http://127.0.0.1:8000{path}?{query}",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
    )
    channel = "wechat" if "wechat" in path else "telegram"
    if not claim_delivery_action(
        connection, report_date=report_date, channel=channel, action="manual_delivery"
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
                action="manual_delivery",
                status="created" if channel == "wechat" else "sent",
            )
            connection.commit()
            return payload
    except Exception as exc:  # noqa: BLE001 - dashboard displays a safe error
        finish_delivery_action(
            connection,
            report_date=report_date,
            channel=channel,
            action="manual_delivery",
            status="failed",
            error_message=type(exc).__name__,
        )
        connection.commit()
        return f"操作失败：{type(exc).__name__}"


def _run_recovery() -> str:
    script = os.environ.get(
        "JOBFLOW_DAILY_UPDATE_SCRIPT", str(Path.cwd() / "ops" / "daily_update.sh")
    )
    working_directory = os.environ.get("JOBFLOW_DIR", str(Path(script).parent.parent))
    try:
        result = subprocess.run(
            [script],
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"恢复运行失败：{type(exc).__name__}"
    if result.returncode:
        return f"恢复运行失败：exit_{result.returncode}"
    return "恢复运行已完成，请继续核对 Telegram 和微信公众号结果"


def main() -> None:
    st.set_page_config(page_title="JobFlow Operations", layout="wide")
    st.title("JobFlow 平台运行与投放控制台")
    admin_token = st.text_input("管理员 Token", type="password")
    authenticated = bool(admin_token and admin_token == os.environ.get("JOBFLOW_ADMIN_TOKEN"))
    config = Path(__file__).parents[3] / "config" / "platform_stages.yaml"
    definitions = load_stage_definitions(config)
    connection = connect_postgres()
    last_checks = st.session_state.get("last_checks", list_recent_checks(connection))
    snapshot = build_stage_snapshot(definitions, stage_evidence(last_checks))
    tab_overview, tab_operations, tab_deliveries = st.tabs(["平台总览", "运行中心", "投放中心"])
    with tab_overview:
        render_overview(snapshot)
    with tab_operations:
        render_operations(connection, authenticated=authenticated)
    with tab_deliveries:
        if authenticated:
            render_deliveries(connection)
        else:
            st.warning("请输入管理员 Token")
    connection.close()


if __name__ == "__main__":
    main()
