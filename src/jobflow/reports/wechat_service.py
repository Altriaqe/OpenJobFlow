"""微信日报服务：编排文章包、渠道状态、令牌和模板发送。"""

from collections.abc import Callable
from datetime import date
import hashlib
import json
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
from jobflow.reports.charts import build_daily_new_jobs_cover_png
from jobflow.reports.wechat_article import WechatArticleData, write_wechat_article
from jobflow.reports.wechat_template import build_wechat_template_data


REPORT_KEY = "multi_keyword_daily"
CHANNEL = "wechat_test_template"


def _article_files(snapshot_date: date) -> tuple[str, ...]:
    """返回指定日期的完整文章包文件名，包括公众号导入专用 Markdown。"""
    return (
        "article.md",
        f"{snapshot_date.isoformat()} 每日新增岗位公告.md",
        "article.html",
        "cover.png",
        "trend.png",
        "manifest.json",
    )


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
    write_wechat_article(
        article_data,
        trend_png,
        build_daily_new_jobs_cover_png(),
        output_dir,
    )
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


def generate_wechat_article_from_snapshots(
    connection,
    *,
    snapshot_date: date,
    runtime_root: Path = Path("runtime"),
) -> dict[str, object]:
    """从真实快照生成本地文章包，不读取微信凭据也不触发网络。"""
    article_data, trend_png = build_multi_keyword_wechat_parts(
        connection,
        snapshot_date=snapshot_date,
    )
    output_dir = runtime_root / "reports" / snapshot_date.isoformat() / "wechat"
    manifest = write_wechat_article(
        article_data,
        trend_png,
        build_daily_new_jobs_cover_png(),
        output_dir,
    )
    return {
        "status": "generated",
        "snapshot_date": snapshot_date.isoformat(),
        "new_job_count": manifest.new_job_count,
        "baseline_ready": all(count is not None for _keyword, count in manifest.keyword_counts),
    }


def get_wechat_article_status(
    *,
    snapshot_date: date,
    runtime_root: Path = Path("runtime"),
) -> dict[str, object]:
    """读取文章包清单并只暴露审核所需的安全状态。"""
    pending = {"status": "pending", "snapshot_date": snapshot_date.isoformat()}
    output_dir = runtime_root / "reports" / snapshot_date.isoformat() / "wechat"
    manifest_path = output_dir / "manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return pending
    if payload.get("report_date") != snapshot_date.isoformat():
        return pending
    article_files = _article_files(snapshot_date)
    if tuple(payload.get("files", ())) != article_files:
        return pending
    if not all((output_dir / filename).is_file() for filename in article_files):
        return pending
    new_job_count = payload.get("new_job_count")
    keyword_counts = payload.get("keyword_counts")
    if not isinstance(new_job_count, int) or new_job_count < 0:
        return pending
    if not isinstance(keyword_counts, list) or not keyword_counts:
        return pending
    parsed_counts: list[int | None] = []
    for item in keyword_counts:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not isinstance(item[0], str)
            or not item[0].strip()
            or (item[1] is not None and (not isinstance(item[1], int) or item[1] < 0))
        ):
            return pending
        parsed_counts.append(item[1])
    if sum(count or 0 for count in parsed_counts) != new_job_count:
        return pending
    cover_digest = payload.get("cover_sha256")
    trend_digest = payload.get("trend_sha256")
    if not isinstance(cover_digest, str) or not isinstance(trend_digest, str):
        return pending
    try:
        actual_cover = hashlib.sha256((output_dir / "cover.png").read_bytes()).hexdigest()
        actual_trend = hashlib.sha256((output_dir / "trend.png").read_bytes()).hexdigest()
    except OSError:
        return pending
    if actual_cover != cover_digest or actual_trend != trend_digest:
        return pending
    return {
        "status": "generated",
        "snapshot_date": snapshot_date.isoformat(),
        "new_job_count": new_job_count,
        "baseline_ready": all(count is not None for count in parsed_counts),
    }
