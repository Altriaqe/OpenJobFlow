from datetime import date
from unittest.mock import Mock

import pytest

from jobflow.db.report_deliveries import ChannelDelivery, claim_delivery, record_delivery_result


def connection_with(delivery: ChannelDelivery):
    cursor = Mock()
    cursor.fetchone.return_value = tuple(delivery.__dict__.values())
    connection = Mock()
    connection.cursor.return_value = cursor
    return connection, cursor


def test_claim_pending_delivery_marks_sending():
    delivery = ChannelDelivery(
        date(2026, 8, 26), "multi_keyword_daily", "wechat", "pending", None, 0, None
    )
    connection, cursor = connection_with(delivery)

    claimed = claim_delivery(
        connection,
        report_date=delivery.report_date,
        report_key=delivery.report_key,
        channel=delivery.channel,
    )

    assert claimed.status == "pending"
    assert any("SET status = 'sending'" in call.args[0] for call in cursor.execute.call_args_list)


def test_uncertain_requires_explicit_permission():
    delivery = ChannelDelivery(
        date(2026, 8, 26), "multi_keyword_daily", "wechat", "uncertain", None, 1, "timeout"
    )
    connection, _cursor = connection_with(delivery)

    with pytest.raises(ValueError, match="uncertain"):
        claim_delivery(
            connection,
            report_date=delivery.report_date,
            report_key=delivery.report_key,
            channel=delivery.channel,
        )


def test_record_result_only_updates_sending_state():
    connection = Mock()
    cursor = Mock()
    connection.cursor.return_value = cursor

    record_delivery_result(
        connection,
        report_date=date(2026, 8, 26),
        report_key="multi_keyword_daily",
        channel="wechat",
        status="sent",
        external_message_id="123",
    )

    sql = cursor.execute.call_args.args[0]
    assert "AND status = 'sending'" in sql
