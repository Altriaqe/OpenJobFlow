"""服务器重启后的固定检查编排。"""

from collections.abc import Callable, Mapping
import subprocess
from urllib.request import urlopen

from jobflow.operations.models import CheckResult


CHECK_NAMES = (
    "tailscale_ssh",
    "xvfb",
    "chrome",
    "x11vnc",
    "daily_timer",
    "postgres",
    "api_container",
    "health",
    "ready",
    "boss_login",
    "latest_etl",
    "telegram",
    "wechat",
)


def run_server_checks(probes: Mapping[str, Callable[[], CheckResult]]) -> tuple[CheckResult, ...]:
    results = []
    for name in CHECK_NAMES:
        probe = probes.get(name)
        if probe is None:
            results.append(CheckResult(name, "failed", "未配置检查项", "probe_not_configured"))
            continue
        try:
            result = probe()
        except Exception as exc:  # noqa: BLE001 - a check must report, not crash the console
            result = CheckResult(name, "failed", "检查执行失败", type(exc).__name__)
        results.append(result)
    return tuple(results)


def command_probe(name: str, command: tuple[str, ...]) -> Callable[[], CheckResult]:
    def probe() -> CheckResult:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        if completed.returncode:
            return CheckResult(name, "failed", "命令返回失败", f"exit_{completed.returncode}")
        return CheckResult(name, "succeeded", "检查通过")

    return probe


def url_probe(name: str, url: str) -> Callable[[], CheckResult]:
    def probe() -> CheckResult:
        with urlopen(url, timeout=5) as response:  # noqa: S310 - URL is a fixed internal endpoint
            if response.status >= 400:
                raise RuntimeError(f"http_{response.status}")
        return CheckResult(name, "succeeded", "检查通过")

    return probe


def database_probe(name: str, connection, query: str) -> Callable[[], CheckResult]:
    def probe() -> CheckResult:
        cursor = connection.cursor()
        cursor.execute(query)
        row = cursor.fetchone()
        if not row or not row[0]:
            return CheckResult(name, "failed", "数据库状态未通过", "state_not_ready")
        return CheckResult(name, "succeeded", "检查通过")

    return probe


def default_probes() -> dict[str, Callable[[], CheckResult]]:
    probes = {
        "tailscale_ssh": command_probe("tailscale_ssh", ("tailscale", "status", "--self")),
    }
    probes.update(
        {
            name: command_probe(name, ("systemctl", "is-active", service))
            for name, service in {
                "xvfb": "jobflow-xvfb.service",
                "chrome": "jobflow-boss-chrome.service",
                "x11vnc": "jobflow-x11vnc.service",
                "daily_timer": "jobflow-daily-update.timer",
            }.items()
        }
    )
    probes.update(
        {
            "api_container": url_probe("api_container", "http://127.0.0.1:8000/health"),
            "health": url_probe("health", "http://127.0.0.1:8000/health"),
            "ready": url_probe("ready", "http://127.0.0.1:8000/ready"),
        }
    )
    return probes
