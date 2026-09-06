from jobflow.operations.checks import CHECK_NAMES, run_server_checks
from jobflow.operations.models import CheckResult


def test_checks_run_in_fixed_order_and_report_missing_probe():
    result = run_server_checks({"health": lambda: CheckResult("health", "succeeded", "ok")})
    assert tuple(item.name for item in result) == CHECK_NAMES
    assert result[0].status == "failed"
    assert result[7].summary == "ok"


def test_probe_exception_is_redacted():
    result = run_server_checks({"health": lambda: (_ for _ in ()).throw(RuntimeError("secret"))})
    assert result[7].error == "RuntimeError"
    assert "secret" not in result[7].summary
