"""运行中心的服务器检查探针。"""

import os
import subprocess

from jobflow.operations.checks import database_probe, default_probes
from jobflow.operations.models import CheckResult


def build_dashboard_probes(connection):
    probes = default_probes()
    probes.update(
        {
            "postgres": database_probe("postgres", connection, "SELECT TRUE"),
            "latest_etl": database_probe(
                "latest_etl", connection,
                "SELECT EXISTS (SELECT 1 FROM ops.batches WHERE status = 'succeeded')",
            ),
            "telegram": database_probe(
                "telegram", connection,
                """SELECT EXISTS (
                    SELECT 1 FROM ops.report_deliveries
                    WHERE status IN ('completed', 'completed_text_uncertain')
                ) OR EXISTS (
                    SELECT 1 FROM ops.report_channel_deliveries
                    WHERE channel = 'telegram' AND status = 'sent'
                )""",
            ),
            "wechat": database_probe(
                "wechat", connection,
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
    return CheckResult(
        "boss_login",
        "succeeded" if result.returncode == 0 else "failed",
        "检查通过" if result.returncode == 0 else "命令返回失败",
        None if result.returncode == 0 else f"exit_{result.returncode}",
    )
