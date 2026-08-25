from unittest.mock import Mock

import pytest

from jobflow.channels.wecom import (
    WeComConfigurationError,
    WeComDeliveryError,
    send_wecom_text,
)


def test_send_wecom_text_posts_expected_payload():
    response = Mock(status_code=200)
    response.json.return_value = {"errcode": 0, "errmsg": "ok"}
    post = Mock(return_value=response)

    send_wecom_text("城市岗位报告", webhook_url="https://example.test/hook", post=post)

    post.assert_called_once_with(
        "https://example.test/hook",
        json={"msgtype": "text", "text": {"content": "城市岗位报告"}},
        timeout=10,
    )


def test_send_wecom_text_requires_webhook(monkeypatch):
    monkeypatch.delenv("WECOM_WEBHOOK_URL", raising=False)

    with pytest.raises(WeComConfigurationError, match="WECOM_WEBHOOK_URL"):
        send_wecom_text("report", post=Mock())


def test_send_wecom_text_rejects_wecom_error_without_exposing_webhook():
    response = Mock(status_code=200)
    response.json.return_value = {"errcode": 93000, "errmsg": "invalid webhook"}
    post = Mock(return_value=response)

    with pytest.raises(WeComDeliveryError, match="WeCom rejected message") as exc_info:
        send_wecom_text("report", webhook_url="https://secret.example/hook", post=post)

    assert "secret.example" not in str(exc_info.value)
