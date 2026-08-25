import os

import requests


class WeComConfigurationError(Exception):
    pass


class WeComDeliveryError(Exception):
    pass


def send_wecom_text(
    report: str,
    *,
    webhook_url: str | None = None,
    post=None,
) -> None:
    selected_webhook = webhook_url or os.getenv("WECOM_WEBHOOK_URL")
    if not selected_webhook:
        raise WeComConfigurationError("missing WECOM_WEBHOOK_URL")

    post_request = post or requests.post
    try:
        response = post_request(
            selected_webhook,
            json={"msgtype": "text", "text": {"content": report}},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise WeComDeliveryError("WeCom request failed") from exc

    if payload.get("errcode") != 0:
        raise WeComDeliveryError("WeCom rejected message")
