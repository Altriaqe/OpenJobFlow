"""微信日报服务：编排文章包、渠道状态、令牌和模板发送。"""

from collections.abc import Callable
from datetime import date
import os
from pathlib import Path

from jobflow.channels.wechat_official import (
    WechatConfigurationError,
    WechatDeliveryError,
    WechatDeliveryUncertain,
    WechatReceipt,
    WechatTokenError,
    get_wechat_access_token,
    send_wechat_template,
)
from jobflow.db.report_deliveries import (
    claim_delivery,
    get_channel_delivery,
    record_delivery_result,
)
from jobflow.reports.multi_keyword_service import build_multi_keyword_wechat_parts
from jobflow.reports.wechat_article import WechatArticleData, write_wechat_article
from jobflow.reports.wechat_template import build_wechat_template_data


REPORT_KEY = "multi_keyword_daily"
CHANNEL = "wechat_test_template"


def _enabled() -> bool:
    return os.getenv("WECHAT_ENABLED", "false").strip().lower() == "true"


def get_wechat_daily_report_status(connection, *, snapshot_date: date) -> dict[str, object]:
    """返回脱敏渠道状态，不暴露消息 ID、接收者或凭据。"""
    delivery = get_channel_delivery(
        connection, report_date=snapshot_date, report_key=REPORT_KEY, channel=CHANNEL
    )
    return {
        "snapshot_date": snapshot_date.isoformat(),
        "enabled": _enabled(),
        "status": "pending" if delivery is None else delivery.status,
        "manual_action_required": delivery is not None and delivery.status == "uncertain",
    }


def send_wechat_report_from_snapshots(
    connection,
    *,
    snapshot_date: date,
    allow_uncertain: bool = False,
) -> dict[str, object]:
    """从数据库快照构建微信日报；默认关闭时安全跳过且不触发网络。"""
    if not _enabled():
        return {"status": "disabled", "snapshot_date": snapshot_date.isoformat()}
    current = get_channel_delivery(
        connection, report_date=snapshot_date, report_key=REPORT_KEY, channel=CHANNEL
    )
    if current is not None and current.status == "sent":
        return {"status": "already_sent", "snapshot_date": snapshot_date.isoformat()}
    article_data, trend_png = build_multi_keyword_wechat_parts(
        connection, snapshot_date=snapshot_date
    )
    output_dir = Path("runtime") / "reports" / snapshot_date.isoformat() / "wechat"
    return send_wechat_daily_report(
        connection,
        article_data=article_data,
        trend_png=trend_png,
        output_dir=output_dir,
        allow_uncertain=allow_uncertain,
    )


def send_wechat_daily_report(
    connection,
    *,
    article_data: WechatArticleData,
    trend_png: bytes,
    output_dir: Path,
    token_loader: Callable[[], str] | None = None,
    template_sender: Callable[[str, dict[str, dict[str, str]]], WechatReceipt] | None = None,
    allow_uncertain: bool = False,
) -> dict[str, object]:
    """生成文章包并发送模板摘要；投递状态与 Telegram 完全独立。"""
    write_wechat_article(article_data, trend_png, output_dir)
    claim_delivery(
        connection,
        report_date=article_data.report_date,
        report_key=REPORT_KEY,
        channel=CHANNEL,
        allow_uncertain=allow_uncertain,
    )
    connection.commit()
    load_token = token_loader or get_wechat_access_token
    send_template = template_sender or (
        lambda token, payload: send_wechat_template(access_token=token, data=payload)
    )
    try:
        token = load_token()
        receipt = send_template(token, build_wechat_template_data(article_data))
    except (WechatConfigurationError, WechatTokenError, WechatDeliveryError) as exc:
        record_delivery_result(
            connection,
            report_date=article_data.report_date,
            report_key=REPORT_KEY,
            channel=CHANNEL,
            status="failed",
            error_type=type(exc).__name__,
        )
        connection.commit()
        raise
    except WechatDeliveryUncertain as exc:
        record_delivery_result(
            connection,
            report_date=article_data.report_date,
            report_key=REPORT_KEY,
            channel=CHANNEL,
            status="uncertain",
            error_type=type(exc).__name__,
        )
        connection.commit()
        raise
    record_delivery_result(
        connection,
        report_date=article_data.report_date,
        report_key=REPORT_KEY,
        channel=CHANNEL,
        status="sent",
        external_message_id=str(receipt.message_id),
    )
    connection.commit()
    return {"status": "sent", "message_id": receipt.message_id}
