from unittest.mock import Mock

import pytest

from jobflow.channels.wechat_official import (
    WechatConfigurationError,
    WechatDeliveryError,
    WechatDeliveryUncertain,
    get_wechat_access_token,
    send_wechat_template,
)


def test_missing_configuration_does_not_issue_request(monkeypatch):
    for name in ("WECHAT_APP_ID", "WECHAT_APP_SECRET", "WECHAT_OPENID", "WECHAT_TEMPLATE_ID"):
        monkeypatch.delenv(name, raising=False)
    get = Mock()

    with pytest.raises(WechatConfigurationError, match="WECHAT_APP_ID"):
        get_wechat_access_token(get=get)

    get.assert_not_called()


def test_get_access_token_returns_token_without_exposing_secret():
    response = Mock(status_code=200)
    response.json.return_value = {"access_token": "access-token", "expires_in": 7200}
    get = Mock(return_value=response)

    token = get_wechat_access_token(app_id="app-id", app_secret="secret-value", get=get)

    assert token == "access-token"
    get.assert_called_once_with(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={"grant_type": "client_credential", "appid": "app-id", "secret": "secret-value"},
        timeout=10,
    )


def test_send_template_returns_message_id():
    response = Mock(status_code=200)
    response.json.return_value = {"errcode": 0, "errmsg": "ok", "msgid": 12345}
    post = Mock(return_value=response)

    receipt = send_wechat_template(
        access_token="access-token",
        openid="openid-value",
        template_id="template-value",
        data={"first": {"value": "日报"}},
        post=post,
    )

    assert receipt.message_id == 12345
    assert receipt.attempts == 1
    post.assert_called_once_with(
        "https://api.weixin.qq.com/cgi-bin/message/template/send?access_token=access-token",
        json={
            "touser": "openid-value",
            "template_id": "template-value",
            "data": {"first": {"value": "日报"}},
        },
        timeout=10,
    )


def test_explicit_wechat_error_is_delivery_error_without_secret():
    response = Mock(status_code=200)
    response.json.return_value = {"errcode": 40001, "errmsg": "invalid credential"}

    with pytest.raises(WechatDeliveryError, match="rejected") as exc_info:
        send_wechat_template(
            access_token="secret-token",
            openid="secret-openid",
            template_id="secret-template",
            data={},
            post=Mock(return_value=response),
        )

    assert "secret-token" not in str(exc_info.value)
    assert "secret-openid" not in str(exc_info.value)
    assert "secret-template" not in str(exc_info.value)


def test_timeout_is_uncertain():
    post = Mock(side_effect=TimeoutError("network timeout"))

    with pytest.raises(WechatDeliveryUncertain):
        send_wechat_template(
            access_token="token", openid="openid", template_id="template", data={}, post=post
        )


def test_http_4xx_is_explicit_delivery_error():
    response = Mock(status_code=400)

    with pytest.raises(WechatDeliveryError, match="rejected"):
        send_wechat_template(
            access_token="token",
            openid="openid",
            template_id="template",
            data={},
            post=Mock(return_value=response),
        )
