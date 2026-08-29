from pathlib import Path
from unittest.mock import Mock

import pytest

from jobflow.channels.wechat_draft import (
    build_draft_payload,
    create_draft,
    upload_image,
)
from jobflow.channels.wechat_official import WechatDeliveryError


def response(payload, status_code=200):
    result = Mock()
    result.status_code = status_code
    result.json.return_value = payload
    result.raise_for_status.return_value = None
    return result


def test_upload_image_returns_media_id_and_url(tmp_path: Path):
    image = tmp_path / "trend.png"
    image.write_bytes(b"png")
    post = Mock(return_value=response({"errcode": 0, "media_id": "media", "url": "https://wx/image"}))

    uploaded = upload_image(access_token="token", path=image, permanent=False, post=post)

    assert uploaded.media_id == "media"
    assert uploaded.url == "https://wx/image"
    assert post.call_args.kwargs["files"]["media"][0] == "trend.png"


def test_build_payload_replaces_local_trend_image():
    payload = build_draft_payload(
        article_html='<img src="trend.png">',
        title="2026-08-29 每日新增岗位公告",
        author="JobFlow",
        digest="今日新增岗位",
        thumb_media_id="cover",
        trend_image_url="https://wx/trend",
    )

    article = payload["articles"][0]
    assert article["thumb_media_id"] == "cover"
    assert article["content"] == '<img src="https://wx/trend">'


def test_build_payload_rejects_unreplaced_local_image():
    with pytest.raises(ValueError, match="local trend image"):
        build_draft_payload(
            article_html="<img src=trend.png>",
            title="title",
            author="author",
            digest="digest",
            thumb_media_id="cover",
            trend_image_url="https://wx/trend",
        )


def test_create_draft_returns_media_id_without_publishing():
    post = Mock(return_value=response({"errcode": 0, "media_id": "draft-media"}))

    draft_id = create_draft(access_token="token", payload={"articles": []}, post=post)

    assert draft_id == "draft-media"
    assert "/cgi-bin/draft/add?" in post.call_args.args[0]


def test_create_draft_maps_wechat_error_without_secret():
    post = Mock(return_value=response({"errcode": 48001, "errmsg": "no permission"}))

    with pytest.raises(WechatDeliveryError, match="rejected"):
        create_draft(access_token="secret-token", payload={"articles": []}, post=post)
