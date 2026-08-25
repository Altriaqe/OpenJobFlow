from unittest.mock import Mock

import pytest
import requests

from jobflow.channels.telegram import (
    TelegramConfigurationError,
    TelegramDeliveryError,
    TelegramDeliveryUncertain,
    TelegramReceipt,
    send_telegram_photo,
    send_telegram_text,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\nimage"


def response(status_code: int = 200, *, message_id: int = 1, payload=None) -> Mock:
    result = Mock(status_code=status_code)
    result.json.return_value = (
        {"ok": True, "result": {"message_id": message_id}} if payload is None else payload
    )
    return result


def test_send_telegram_text_posts_expected_payload():
    post = Mock(return_value=response(message_id=7))

    receipt = send_telegram_text(
        "城市岗位报告",
        bot_token="bot-token",
        chat_id="12345",
        post=post,
        sleep=Mock(),
    )

    assert receipt == TelegramReceipt(message_id=7, attempts=1)
    post.assert_called_once_with(
        "https://api.telegram.org/botbot-token/sendMessage",
        json={"chat_id": "12345", "text": "城市岗位报告"},
        timeout=10,
    )


def test_send_telegram_text_requires_bot_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(TelegramConfigurationError, match="TELEGRAM_BOT_TOKEN"):
        send_telegram_text("report", chat_id="12345", post=Mock())


def test_send_telegram_text_requires_chat_id(monkeypatch):
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(TelegramConfigurationError, match="TELEGRAM_CHAT_ID"):
        send_telegram_text("report", bot_token="bot-token", post=Mock())


def test_send_telegram_text_hides_token_when_request_fails():
    post = Mock(side_effect=RuntimeError("network failed"))

    with pytest.raises(TelegramDeliveryUncertain) as exc_info:
        send_telegram_text(
            "report",
            bot_token="secret-bot-token",
            chat_id="12345",
            post=post,
        )

    assert "secret-bot-token" not in str(exc_info.value)


def test_send_telegram_text_rejects_unsuccessful_response_without_details():
    post = Mock(
        return_value=response(
            payload={"ok": False, "description": "secret response detail"},
        )
    )

    with pytest.raises(TelegramDeliveryError) as exc_info:
        send_telegram_text(
            "report",
            bot_token="secret-bot-token",
            chat_id="12345",
            post=post,
        )

    assert "secret response detail" not in str(exc_info.value)
    assert "secret-bot-token" not in str(exc_info.value)


def test_send_telegram_text_rejects_report_over_telegram_limit():
    post = Mock()

    with pytest.raises(TelegramDeliveryError, match="message is too long"):
        send_telegram_text(
            "x" * 4097,
            bot_token="bot-token",
            chat_id="12345",
            post=post,
        )

    post.assert_not_called()


def test_send_telegram_photo_uploads_png_and_returns_message_id() -> None:
    post = Mock(return_value=response(message_id=27))

    receipt = send_telegram_photo(
        PNG_BYTES,
        bot_token="bot-token",
        chat_id="12345",
        post=post,
        sleep=Mock(),
    )

    assert receipt == TelegramReceipt(message_id=27, attempts=1)
    _, kwargs = post.call_args
    assert kwargs["data"] == {"chat_id": "12345"}
    assert kwargs["files"]["photo"][0] == "jobflow-city-share.png"
    assert kwargs["files"]["photo"][2] == "image/png"


def test_send_telegram_photo_retries_5xx_three_times() -> None:
    post = Mock(side_effect=[response(500), response(503), response(message_id=9)])
    sleep = Mock()

    receipt = send_telegram_photo(
        PNG_BYTES,
        bot_token="bot-token",
        chat_id="1",
        post=post,
        sleep=sleep,
    )

    assert receipt == TelegramReceipt(9, 3)
    assert post.call_count == 3
    assert sleep.call_count == 2


def test_unauthorized_response_is_not_retried_or_exposed() -> None:
    unauthorized_post = Mock(
        return_value=response(
            401,
            payload={"ok": False, "description": "secret response detail"},
        )
    )

    with pytest.raises(TelegramDeliveryError) as exc_info:
        send_telegram_text(
            "报告",
            bot_token="secret-bot-token",
            chat_id="1",
            post=unauthorized_post,
            sleep=Mock(),
        )

    assert unauthorized_post.call_count == 1
    assert exc_info.value.attempts == 1
    assert "secret-bot-token" not in str(exc_info.value)
    assert "secret response detail" not in str(exc_info.value)


def test_timeout_is_retried_then_returns_attempt_count() -> None:
    post = Mock(side_effect=[requests.Timeout("secret-bot-token"), response(message_id=8)])
    sleep = Mock()

    receipt = send_telegram_text(
        "报告",
        bot_token="secret-bot-token",
        chat_id="1",
        post=post,
        sleep=sleep,
    )

    assert receipt == TelegramReceipt(8, 2)
    assert post.call_count == 2
    sleep.assert_called_once_with(1)


@pytest.mark.parametrize(
    "failure",
    [
        requests.Timeout("secret"),
        requests.ConnectionError("secret"),
    ],
)
def test_single_attempt_network_failure_is_uncertain(failure) -> None:
    post = Mock(side_effect=failure)

    with pytest.raises(TelegramDeliveryUncertain) as exc_info:
        send_telegram_text(
            "报告",
            bot_token="secret-bot-token",
            chat_id="1",
            post=post,
            sleep=Mock(),
            max_attempts=1,
        )

    post.assert_called_once()
    assert exc_info.value.attempts == 1
    assert "secret" not in str(exc_info.value)


def test_single_attempt_server_error_is_uncertain() -> None:
    post = Mock(return_value=response(503))

    with pytest.raises(TelegramDeliveryUncertain) as exc_info:
        send_telegram_photo(
            PNG_BYTES,
            bot_token="bot-token",
            chat_id="1",
            post=post,
            sleep=Mock(),
            max_attempts=1,
        )

    post.assert_called_once()
    assert exc_info.value.attempts == 1


def test_malformed_success_payload_is_uncertain() -> None:
    post = Mock(return_value=response(payload={"ok": True, "result": {}}))

    with pytest.raises(TelegramDeliveryUncertain, match="uncertain"):
        send_telegram_text(
            "报告",
            bot_token="bot-token",
            chat_id="1",
            post=post,
            sleep=Mock(),
            max_attempts=1,
        )

    post.assert_called_once()


def test_photo_validation_happens_before_network_call() -> None:
    post = Mock()

    with pytest.raises(TelegramDeliveryError, match="PNG"):
        send_telegram_photo(
            b"not-an-image", bot_token="bot-token", chat_id="1", post=post, sleep=Mock()
        )

    post.assert_not_called()
