import os
import time
from dataclasses import dataclass
from typing import Callable

import requests


class TelegramConfigurationError(Exception):
    pass


class TelegramDeliveryError(Exception):
    def __init__(self, message: str, *, attempts: int = 1) -> None:
        super().__init__(message)
        self.attempts = attempts


class TelegramDeliveryUncertain(Exception):
    """Telegram 可能已经接收消息，但 JobFlow 没有取得可信回执。"""

    def __init__(self, message: str, *, attempts: int = 1) -> None:
        super().__init__(message)
        self.attempts = attempts


@dataclass(frozen=True)
class TelegramReceipt:
    message_id: int
    attempts: int


TELEGRAM_MESSAGE_LIMIT = 4096


def send_telegram_text(
    report: str,
    *,
    bot_token: str | None = None,
    chat_id: str | None = None,
    post=None,
    sleep=time.sleep,
    max_attempts: int = 3,
) -> TelegramReceipt:
    selected_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    selected_chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not selected_token:
        raise TelegramConfigurationError("missing TELEGRAM_BOT_TOKEN")
    if not selected_chat_id:
        raise TelegramConfigurationError("missing TELEGRAM_CHAT_ID")
    if len(report) > TELEGRAM_MESSAGE_LIMIT:
        raise TelegramDeliveryError("Telegram message is too long")

    url = f"https://api.telegram.org/bot{selected_token}/sendMessage"

    def request():
        return (post or requests.post)(
            url,
            json={"chat_id": selected_chat_id, "text": report},
            timeout=10,
        )

    return _request_telegram(request=request, max_attempts=max_attempts, sleep=sleep)


def send_telegram_photo(
    photo: bytes,
    *,
    filename: str = "jobflow-city-share.png",
    bot_token: str | None = None,
    chat_id: str | None = None,
    post=None,
    sleep=time.sleep,
    max_attempts: int = 3,
) -> TelegramReceipt:
    selected_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    selected_chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not selected_token:
        raise TelegramConfigurationError("missing TELEGRAM_BOT_TOKEN")
    if not selected_chat_id:
        raise TelegramConfigurationError("missing TELEGRAM_CHAT_ID")
    if not filename.strip():
        raise TelegramDeliveryError("Telegram photo filename is empty")
    if not photo.startswith(b"\x89PNG\r\n\x1a\n"):
        raise TelegramDeliveryError("Telegram photo must be a PNG")

    url = f"https://api.telegram.org/bot{selected_token}/sendPhoto"

    def request():
        return (post or requests.post)(
            url,
            data={"chat_id": selected_chat_id},
            files={"photo": (filename, photo, "image/png")},
            timeout=20,
        )

    return _request_telegram(request=request, max_attempts=max_attempts, sleep=sleep)


def _request_telegram(
    *,
    request: Callable[[], object],
    max_attempts: int,
    sleep: Callable[[int], object],
) -> TelegramReceipt:
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    for attempt in range(1, max_attempts + 1):
        try:
            response = request()
            status_code = response.status_code
            if status_code >= 500:
                if attempt < max_attempts:
                    sleep(attempt)
                    continue
                raise TelegramDeliveryUncertain(
                    "Telegram delivery result is uncertain",
                    attempts=attempt,
                )
            if 400 <= status_code < 500:
                raise TelegramDeliveryError("Telegram request rejected", attempts=attempt)
            response.raise_for_status()
            payload = response.json()
        except TelegramDeliveryError:
            raise
        except TelegramDeliveryUncertain:
            raise
        except requests.RequestException:
            if attempt < max_attempts:
                sleep(attempt)
                continue
            raise TelegramDeliveryUncertain(
                "Telegram delivery result is uncertain",
                attempts=attempt,
            ) from None
        except Exception:
            if attempt < max_attempts:
                sleep(attempt)
                continue
            raise TelegramDeliveryUncertain(
                "Telegram delivery result is uncertain",
                attempts=attempt,
            ) from None

        message_id = (
            payload.get("result", {}).get("message_id") if isinstance(payload, dict) else None
        )
        if isinstance(payload, dict) and payload.get("ok") is False:
            raise TelegramDeliveryError("Telegram rejected message", attempts=attempt)
        if (
            not isinstance(payload, dict)
            or payload.get("ok") is not True
            or not isinstance(message_id, int)
            or message_id <= 0
        ):
            if attempt < max_attempts:
                sleep(attempt)
                continue
            raise TelegramDeliveryUncertain(
                "Telegram delivery result is uncertain",
                attempts=attempt,
            )
        return TelegramReceipt(message_id=message_id, attempts=attempt)

    raise TelegramDeliveryUncertain(
        "Telegram delivery result is uncertain",
        attempts=max_attempts,
    )
