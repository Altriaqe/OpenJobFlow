"""日报 HTTP 入口：鉴权后调用报告服务，不在路由层重复统计。"""

import os
import secrets
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jobflow.ai.openai_summary import OpenAIConfigurationError, OpenAISummaryError
from jobflow.api.analytics import get_connection
from jobflow.channels.telegram import (
    TelegramConfigurationError,
    TelegramDeliveryError,
    TelegramDeliveryUncertain,
)
from jobflow.reports.service import send_city_report
from jobflow.reports.daily_service import (
    DailySnapshotNotFound,
    get_daily_report_status,
    send_daily_report,
)
from jobflow.reports.multi_keyword_service import (
    MultiKeywordDeliveryStateError,
    MultiKeywordSnapshotMissing,
    get_multi_keyword_report_status,
    recover_multi_keyword_report_photo,
    send_multi_keyword_report,
)

router = APIRouter(prefix="/reports")
bearer = HTTPBearer(auto_error=False)

# 这些小型 provider 让测试可以替换发送器和状态读取器，避免触发真实外部服务。


def get_report_sender():
    return send_city_report


def get_daily_report_sender():
    return send_daily_report


def get_daily_status_reader():
    return get_daily_report_status


def get_multi_daily_report_sender():
    return send_multi_keyword_report


def get_multi_daily_status_reader():
    return get_multi_keyword_report_status


def get_multi_daily_photo_recoverer():
    return recover_multi_keyword_report_photo


def require_report_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> None:
    """校验报告接口 Bearer Token；失败只返回通用鉴权错误。"""
    expected = os.getenv("REPORT_TRIGGER_TOKEN")
    provided = credentials.credentials if credentials else ""
    if not expected or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid report trigger token")


@router.post("/cities/send", dependencies=[Depends(require_report_token)])
def send_cities_report(
    mode: Literal["query", "ai"] = "query",
    connection=Depends(get_connection),
    report_sender=Depends(get_report_sender),
):
    """触发城市日报发送，路由只负责鉴权、参数和异常映射。"""
    try:
        return report_sender(connection, mode=mode)
    except TelegramDeliveryError as exc:
        raise HTTPException(status_code=502, detail="report delivery failed") from exc
    except (
        OpenAIConfigurationError,
        OpenAISummaryError,
        TelegramConfigurationError,
    ) as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc


@router.get("/daily/status", dependencies=[Depends(require_report_token)])
def daily_report_status(
    snapshot_date: date,
    keyword: str = "AI Agent",
    connection=Depends(get_connection),
    status_reader=Depends(get_daily_status_reader),
):
    """读取单关键词日报状态，不重新执行发送。"""
    try:
        return status_reader(connection, snapshot_date=snapshot_date, keyword=keyword)
    except DailySnapshotNotFound as exc:
        raise HTTPException(status_code=404, detail="daily snapshot not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc


@router.post("/daily/send", dependencies=[Depends(require_report_token)])
def send_daily_snapshot_report(
    snapshot_date: date,
    keyword: str = "AI Agent",
    connection=Depends(get_connection),
    report_sender=Depends(get_daily_report_sender),
):
    """触发指定日期快照日报，并将投递状态转换为 HTTP 响应。"""
    try:
        return report_sender(connection, snapshot_date=snapshot_date, keyword=keyword)
    except DailySnapshotNotFound as exc:
        raise HTTPException(status_code=404, detail="daily snapshot not found") from exc
    except TelegramDeliveryError as exc:
        raise HTTPException(status_code=502, detail="report delivery failed") from exc
    except TelegramConfigurationError as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc


@router.get("/daily/multi/status", dependencies=[Depends(require_report_token)])
def multi_daily_report_status(
    snapshot_date: date,
    connection=Depends(get_connection),
    status_reader=Depends(get_multi_daily_status_reader),
):
    """读取多关键词日报的聚合投递状态。"""
    try:
        return status_reader(connection, snapshot_date=snapshot_date)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc


@router.post("/daily/multi/send", dependencies=[Depends(require_report_token)])
def send_multi_daily_snapshot_report(
    snapshot_date: date,
    connection=Depends(get_connection),
    report_sender=Depends(get_multi_daily_report_sender),
):
    """触发多关键词图文日报，保留投递结果不确定的人工恢复语义。"""
    try:
        return report_sender(connection, snapshot_date=snapshot_date)
    except MultiKeywordSnapshotMissing as exc:
        raise HTTPException(status_code=409, detail="daily snapshots incomplete") from exc
    except MultiKeywordDeliveryStateError as exc:
        raise HTTPException(
            status_code=409,
            detail="report delivery requires manual action",
        ) from exc
    except (TelegramDeliveryError, TelegramDeliveryUncertain) as exc:
        raise HTTPException(status_code=502, detail="report delivery failed") from exc
    except TelegramConfigurationError as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc


@router.post("/daily/multi/recover-photo", dependencies=[Depends(require_report_token)])
def recover_multi_daily_snapshot_photo(
    snapshot_date: date,
    confirm_text_visible: bool = False,
    connection=Depends(get_connection),
    photo_recoverer=Depends(get_multi_daily_photo_recoverer),
):
    """在调用者确认未收到文字后，执行受保护的图片补发。"""
    if not confirm_text_visible:
        raise HTTPException(status_code=409, detail="visible text confirmation required")
    try:
        return photo_recoverer(
            connection,
            snapshot_date=snapshot_date,
            confirm_text_visible=True,
        )
    except MultiKeywordSnapshotMissing as exc:
        raise HTTPException(status_code=409, detail="daily snapshots incomplete") from exc
    except MultiKeywordDeliveryStateError as exc:
        raise HTTPException(
            status_code=409,
            detail="report delivery requires manual action",
        ) from exc
    except (TelegramDeliveryError, TelegramDeliveryUncertain) as exc:
        raise HTTPException(status_code=502, detail="report delivery failed") from exc
    except TelegramConfigurationError as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc
