"""平台看板使用的纯数据模型。"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

import yaml


class StageState(StrEnum):
    NOT_STARTED = "未开始"
    IN_PROGRESS = "开发中"
    COMPLETED = "已完成"
    ACCEPTED = "已验收"
    OBSERVING = "观察中"
    ERROR = "异常"


class Channel(StrEnum):
    TELEGRAM = "telegram"
    WECHAT = "wechat"


class OperationKind(StrEnum):
    SERVER_CHECK = "server_check"
    RECOVERY_RUN = "recovery_run"


@dataclass(frozen=True)
class StageDefinition:
    id: str
    name: str
    goal: str
    acceptance: str


@dataclass(frozen=True)
class StageEvidence:
    implemented: bool = False
    accepted: bool = False
    observing: bool = False
    error: bool = False


@dataclass(frozen=True)
class StageSnapshot:
    definition: StageDefinition
    state: StageState


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    summary: str
    error: str | None = None


@dataclass(frozen=True)
class DeliveryResult:
    channel: Channel
    report_date: date
    status: str
    error: str | None = None


@dataclass(frozen=True)
class RecoveryResult:
    status: str
    report_date: date
    steps: tuple[str, ...]


def load_stage_definitions(path: Path) -> tuple[StageDefinition, ...]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    stages = payload.get("stages") if isinstance(payload, dict) else None
    if not isinstance(stages, list) or len(stages) != 8:
        raise ValueError("platform stage configuration must contain exactly eight stages")
    return tuple(StageDefinition(**stage) for stage in stages)
