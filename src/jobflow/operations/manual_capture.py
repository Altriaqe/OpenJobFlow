"""通过共享运行目录请求宿主机执行当天抓取。"""

import os
import json
import time
from datetime import date
from pathlib import Path


class TodayCaptureNotConfigured(Exception):
    pass


class TodayCaptureFailed(Exception):
    pass


def capture_today(snapshot_date: date) -> None:
    root = Path(os.getenv("JOBFLOW_CAPTURE_QUEUE", "runtime/manual-capture"))
    root.mkdir(parents=True, exist_ok=True)
    name = snapshot_date.isoformat()
    request = root / f"{name}.request"
    result = root / f"{name}.result"
    result.unlink(missing_ok=True)
    temporary = root / f".{name}.request.tmp"
    temporary.write_text(json.dumps({"snapshot_date": name}), encoding="utf-8")
    os.replace(temporary, request)
    deadline = time.monotonic() + int(os.getenv("JOBFLOW_CAPTURE_TIMEOUT", "660"))
    while time.monotonic() < deadline:
        if result.exists():
            status = result.read_text(encoding="utf-8").strip()
            result.unlink(missing_ok=True)
            if status == "succeeded":
                return
            raise TodayCaptureFailed
        time.sleep(2)
    raise TodayCaptureNotConfigured
