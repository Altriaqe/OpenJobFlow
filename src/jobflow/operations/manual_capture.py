"""执行服务器预先配置的当天抓取命令。"""

import os
import subprocess
from datetime import date


class TodayCaptureNotConfigured(Exception):
    pass


class TodayCaptureFailed(Exception):
    pass


def capture_today(snapshot_date: date) -> None:
    command = os.getenv("JOBFLOW_TODAY_CAPTURE_COMMAND")
    if not command:
        raise TodayCaptureNotConfigured
    environment = os.environ | {"JOBFLOW_SNAPSHOT_DATE": snapshot_date.isoformat()}
    result = subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=environment,
    )
    if result.returncode != 0:
        raise TodayCaptureFailed
