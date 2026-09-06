from datetime import date

from jobflow.operations.models import CheckResult
from jobflow.operations.runs import run_recovery


DAY = date(2026, 9, 5)


def test_recovery_is_blocked_when_check_fails():
    called = []
    result = run_recovery(
        lambda: (CheckResult("ready", "failed", "no"),),
        lambda _: called.append("etl"),
        lambda _: None,
        lambda _: None,
        DAY,
    )
    assert result.status == "blocked"
    assert called == []


def test_recovery_records_channel_failures_independently():
    result = run_recovery(
        lambda: (CheckResult("ready", "succeeded", "ok"),),
        lambda _: None,
        lambda _: (_ for _ in ()).throw(RuntimeError()),
        lambda _: None,
        DAY,
    )
    assert result.status == "failed"
    assert "telegram_failed" in result.steps
    assert "wechat_succeeded" in result.steps
