"""Official WeChat test-account template delivery."""

from dataclasses import dataclass
import os
from typing import Callable
from urllib.parse import urlencode

import requests


class WechatConfigurationError(Exception):
    pass


class WechatTokenError(Exception):
    pass


class WechatDeliveryError(Exception):
    pass


class WechatDeliveryUncertain(Exception):
    pass


@dataclass(frozen=True)
class WechatReceipt:
    message_id: int
    attempts: int


WECHAT_API_BASE = "https://api.weixin.qq.com"


def _required(value: str | None, env_name: str) -> str:
    """优先使用显式参数，否则读取环境变量，并统一拒绝空配置。"""
    selected = value or os.getenv(env_name)
    if not selected:
        raise WechatConfigurationError(f"missing {env_name}")
    return selected


def get_wechat_access_token(
    *,
    app_id: str | None = None,
    app_secret: str | None = None,
    get: Callable[..., object] | None = None,
    max_attempts: int = 2,
) -> str:
    """向微信官方接口申请短期令牌。

    令牌请求没有消息发送副作用，因此临时网络错误可以有限重试；
    错误文本只使用固定描述，避免把 appsecret 或请求细节写入日志。
    """
    selected_app_id = _required(app_id, "WECHAT_APP_ID")
    selected_secret = _required(app_secret, "WECHAT_APP_SECRET")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    # 通过参数注入 HTTP 函数，离线测试不需要访问微信网络。
    request_get = get or requests.get
    for attempt in range(1, max_attempts + 1):
        try:
            # API 地址固定为官方域名，不允许配置覆盖，减少凭据误发风险。
            response = request_get(
                f"{WECHAT_API_BASE}/cgi-bin/token",
                params={
                    "grant_type": "client_credential",
                    "appid": selected_app_id,
                    "secret": selected_secret,
                },
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            token = payload.get("access_token") if isinstance(payload, dict) else None
            if isinstance(token, str) and token:
                return token
            raise WechatTokenError("WeChat token response is invalid")
        except WechatTokenError:
            raise
        except requests.RequestException as exc:
            if attempt == max_attempts:
                raise WechatTokenError("WeChat token request failed") from exc
        except (TimeoutError, ValueError, TypeError) as exc:
            if attempt == max_attempts:
                raise WechatTokenError("WeChat token response is invalid") from exc

    raise WechatTokenError("WeChat token request failed")


def send_wechat_template(
    *,
    access_token: str,
    openid: str | None = None,
    template_id: str | None = None,
    data: dict[str, object],
    post: Callable[..., object] | None = None,
) -> WechatReceipt:
    """发送一条测试号模板消息，并返回可用于幂等记录的消息 ID。

    请求已经发出但回执不可信时必须抛出 ``WechatDeliveryUncertain``；
    上层不能把这种结果当成明确失败自动重发。
    """
    selected_openid = _required(openid, "WECHAT_OPENID")
    selected_template = _required(template_id, "WECHAT_TEMPLATE_ID")
    if not access_token:
        raise WechatConfigurationError("missing access token")

    # access_token 只放在请求 URL 中，异常信息不会携带该 URL。
    url = f"{WECHAT_API_BASE}/cgi-bin/message/template/send?{urlencode({'access_token': access_token})}"
    try:
        response = (post or requests.post)(
            url,
            json={"touser": selected_openid, "template_id": selected_template, "data": data},
            timeout=10,
        )
        if response.status_code >= 500:
            raise WechatDeliveryUncertain("WeChat delivery result is uncertain")
        if response.status_code >= 400:
            raise WechatDeliveryError("WeChat request rejected")
        response.raise_for_status()
        payload = response.json()
    except WechatDeliveryUncertain:
        raise
    except WechatDeliveryError:
        raise
    except requests.RequestException as exc:
        raise WechatDeliveryUncertain("WeChat delivery result is uncertain") from exc
    except (TimeoutError, ValueError, TypeError) as exc:
        raise WechatDeliveryUncertain("WeChat delivery result is uncertain") from exc

    if not isinstance(payload, dict) or payload.get("errcode") != 0:
        raise WechatDeliveryError("WeChat rejected template message")
    message_id = payload.get("msgid")
    if not isinstance(message_id, int) or message_id <= 0:
        raise WechatDeliveryUncertain("WeChat delivery result is uncertain")
    return WechatReceipt(message_id=message_id, attempts=1)
