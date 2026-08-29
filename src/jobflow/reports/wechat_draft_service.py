"""把已生成的公众号文章包转换为微信草稿；不触发正式发布。"""

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import re

from jobflow.channels.wechat_draft import (
    build_draft_payload,
    create_draft,
    get_wechat_access_token,
    upload_image,
)
from jobflow.db.wechat_drafts import (
    claim_wechat_draft,
    get_wechat_draft_status,
    record_wechat_draft_created,
    record_wechat_draft_failed,
)


@dataclass(frozen=True)
class DraftResult:
    """只向调用方返回审核所需的安全状态。"""

    snapshot_date: date
    status: str
    has_draft: bool = False
    error_code: str | None = None


_REQUIRED_FILES = ("article.html", "cover.png", "trend.png", "manifest.json")


def _load_package(article_dir: Path, report_date: date) -> tuple[str, str]:
    """校验清单、文件和摘要，返回正文 HTML 与文章标题。"""
    try:
        manifest = json.loads((article_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("article manifest is invalid") from exc
    expected_files = tuple(manifest.get("files", ())) if isinstance(manifest, dict) else ()
    if manifest.get("report_date") != report_date.isoformat() or not all(
        filename in expected_files for filename in _REQUIRED_FILES
    ):
        raise ValueError("article manifest does not match report date")
    if any(not (article_dir / filename).is_file() for filename in _REQUIRED_FILES):
        raise ValueError("article package is incomplete")
    for image_name, digest_name in (("cover.png", "cover_sha256"), ("trend.png", "trend_sha256")):
        digest = manifest.get(digest_name)
        actual = hashlib.sha256((article_dir / image_name).read_bytes()).hexdigest()
        if not isinstance(digest, str) or digest != actual:
            raise ValueError("article package image checksum is invalid")
    html = (article_dir / "article.html").read_text(encoding="utf-8")
    match = re.search(r"<h1>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"<[^>]+>", "", match.group(1)).strip() if match else ""
    if not title:
        raise ValueError("article title is missing")
    return html, title


def create_wechat_draft_from_article(
    connection,
    *,
    report_date: date,
    article_dir: Path,
    author: str,
) -> DraftResult:
    """创建单日草稿；失败记录后停止，不自动重试。"""
    current = get_wechat_draft_status(connection, report_date=report_date)
    if current is not None:
        return DraftResult(
            report_date,
            current.status,
            current.status == "created",
            current.error_code,
        )
    if not author.strip():
        raise ValueError("draft author is required")
    if not claim_wechat_draft(connection, report_date=report_date):
        current = get_wechat_draft_status(connection, report_date=report_date)
        return DraftResult(report_date, current.status if current else "uploading")
    connection.commit()
    try:
        article_html, title = _load_package(Path(article_dir), report_date)
        token = get_wechat_access_token()
        cover = upload_image(access_token=token, path=Path(article_dir) / "cover.png", permanent=True)
        trend = upload_image(access_token=token, path=Path(article_dir) / "trend.png", permanent=False)
        if not trend.url:
            raise ValueError("trend image URL is missing")
        payload = build_draft_payload(
            article_html=article_html,
            title=title,
            author=author,
            digest=f"{report_date.isoformat()} 每日新增岗位公告",
            thumb_media_id=cover.media_id,
            trend_image_url=trend.url,
        )
        draft_id = create_draft(access_token=token, payload=payload)
        record_wechat_draft_created(
            connection,
            report_date=report_date,
            draft_media_id=draft_id,
            cover_media_id=cover.media_id,
            trend_media_id=trend.media_id,
        )
        connection.commit()
        return DraftResult(report_date, "created", True)
    except Exception as exc:
        error_code = "article_package_invalid" if isinstance(exc, ValueError) else "wechat_draft_failed"
        record_wechat_draft_failed(
            connection,
            report_date=report_date,
            error_code=error_code,
            error_message="article package validation failed" if error_code == "article_package_invalid" else "WeChat draft creation failed",
        )
        connection.commit()
        return DraftResult(report_date, "failed", False, error_code)


__all__ = ["DraftResult", "create_wechat_draft_from_article"]
