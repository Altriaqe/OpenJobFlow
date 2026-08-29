"""微信公众号素材上传和草稿创建客户端。"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

import requests

from jobflow.channels.wechat_official import (
    WECHAT_API_BASE,
    WechatDeliveryError,
    get_wechat_access_token,
)


@dataclass(frozen=True)
class UploadedWechatImage:
    media_id: str | None = None
    url: str | None = None


def upload_image(
    *,
    access_token: str,
    path: Path,
    permanent: bool,
    post: Callable[..., object] | None = None,
) -> UploadedWechatImage:
    """上传封面或正文图片；返回平台 ID/正文可用 URL。"""
    if not access_token:
        raise WechatDeliveryError("WeChat draft access token is missing")
    if not path.is_file():
        raise WechatDeliveryError("WeChat draft image is missing")
    endpoint = "/cgi-bin/material/add_material" if permanent else "/cgi-bin/media/uploadimg"
    params = {"access_token": access_token}
    if permanent:
        params["type"] = "image"
    try:
        with path.open("rb") as handle:
            response = (post or requests.post)(
                f"{WECHAT_API_BASE}{endpoint}?{urlencode(params)}",
                files={"media": (path.name, handle, "image/png")},
                timeout=30,
            )
        response.raise_for_status()
        payload = response.json()
    except (OSError, requests.RequestException, ValueError, TypeError) as exc:
        raise WechatDeliveryError("WeChat image upload failed") from exc
    if not isinstance(payload, dict) or payload.get("errcode", 0) != 0:
        raise WechatDeliveryError("WeChat image upload rejected")
    media_id = payload.get("media_id")
    url = payload.get("url")
    selected_media_id = media_id if isinstance(media_id, str) and media_id else None
    selected_url = url if isinstance(url, str) and url else None
    # 永久素材接口返回 media_id，正文图片接口 uploadimg 返回可嵌入正文的 url；
    # 两种接口不能用同一个必填字段校验，否则会误判微信的正常响应。
    if permanent and selected_media_id is None:
        raise WechatDeliveryError("WeChat permanent image response is invalid")
    if not permanent and selected_url is None:
        raise WechatDeliveryError("WeChat article image response is invalid")
    return UploadedWechatImage(media_id=selected_media_id, url=selected_url)


def build_draft_payload(
    *,
    article_html: str,
    title: str,
    author: str,
    digest: str,
    thumb_media_id: str,
    trend_image_url: str,
) -> dict[str, object]:
    """构造草稿请求；只替换已知本地趋势图引用。"""
    if not all(isinstance(value, str) and value.strip() for value in (title, author, digest)):
        raise ValueError("draft title, author and digest are required")
    if not thumb_media_id or not trend_image_url:
        raise ValueError("draft media identifiers and trend URL are required")
    content = article_html.replace('src="trend.png"', f'src="{trend_image_url}"')
    content = content.replace("src='trend.png'", f"src='{trend_image_url}'")
    if "trend.png" in content:
        raise ValueError("draft content still contains a local trend image")
    return {
        "articles": [
            {
                "title": title,
                "author": author,
                "digest": digest,
                "content": content,
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            }
        ]
    }


def create_draft(
    *, access_token: str, payload: dict[str, object], post: Callable[..., object] | None = None
) -> str:
    """创建公众号草稿并返回 draft_media_id，不执行发布。"""
    if not access_token:
        raise WechatDeliveryError("WeChat draft access token is missing")
    try:
        response = (post or requests.post)(
            f"{WECHAT_API_BASE}/cgi-bin/draft/add?{urlencode({'access_token': access_token})}",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise WechatDeliveryError("WeChat draft request failed") from exc
    if not isinstance(result, dict) or result.get("errcode", 0) != 0:
        raise WechatDeliveryError("WeChat draft creation rejected")
    media_id = result.get("media_id")
    if not isinstance(media_id, str) or not media_id:
        raise WechatDeliveryError("WeChat draft response is invalid")
    return media_id


__all__ = [
    "UploadedWechatImage",
    "build_draft_payload",
    "create_draft",
    "get_wechat_access_token",
    "upload_image",
]
