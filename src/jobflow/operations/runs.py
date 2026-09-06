"""服务器检查和恢复运行的业务编排。"""

from collections.abc import Callable
from datetime import date

from jobflow.operations.models import CheckResult, RecoveryResult


def run_recovery(
    restart_check: Callable[[], tuple[CheckResult, ...]],
    snapshot_runner: Callable[[date], None],
    telegram_runner: Callable[[date], None],
    wechat_runner: Callable[[date], None],
    report_date: date,
) -> RecoveryResult:
    checks = restart_check()
    if any(result.status != "succeeded" for result in checks):
        return RecoveryResult("blocked", report_date, ("server_check_failed",))
    steps = ["server_check"]
    try:
        snapshot_runner(report_date)
        steps.append("etl_succeeded")
    except Exception:  # noqa: BLE001 - dashboard returns a safe step result
        return RecoveryResult("failed", report_date, tuple(steps + ["etl_failed"]))
    for name, runner in (
        ("telegram_succeeded", telegram_runner),
        ("wechat_succeeded", wechat_runner),
    ):
        try:
            runner(report_date)
            steps.append(name)
        except Exception:
            steps.append(name.removesuffix("_succeeded") + "_failed")
    status = (
        "succeeded"
        if all(step.endswith("_succeeded") or step == "server_check" for step in steps)
        else "failed"
    )
    return RecoveryResult(status, report_date, tuple(steps))
