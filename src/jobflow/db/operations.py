"""平台运行、检查和手动投放记录的参数化数据库操作。"""

from datetime import date
from jobflow.operations.models import CheckResult


def create_operation_run(connection, *, kind: str, report_date: date | None = None) -> int:
    cursor = connection.cursor()
    cursor.execute(
        """INSERT INTO ops.platform_operation_runs (kind, report_date)
        VALUES (%s, %s) RETURNING id""",
        (kind, report_date),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("operation run was not created")
    return row[0]


def finish_operation_run(
    connection, *, operation_id: int, status: str, error_message: str | None = None
) -> None:
    if status not in {"succeeded", "failed"}:
        raise ValueError("invalid operation status")
    connection.cursor().execute(
        """UPDATE ops.platform_operation_runs
        SET status = %s, error_message = %s, finished_at = CURRENT_TIMESTAMP
        WHERE id = %s""",
        (status, error_message, operation_id),
    )


def record_check_result(connection, *, operation_id: int, result) -> None:
    connection.cursor().execute(
        """INSERT INTO ops.platform_check_results
        (operation_id, check_name, status, summary, error_message)
        VALUES (%s, %s, %s, %s, %s)""",
        (operation_id, result.name, result.status, result.summary, result.error),
    )


def record_delivery_action(
    connection,
    *,
    operation_id: int | None,
    report_date: date,
    channel: str,
    action: str,
    status: str,
    error_message: str | None = None,
) -> bool:
    cursor = connection.cursor()
    cursor.execute(
        """INSERT INTO ops.platform_delivery_actions
        (operation_id, report_date, channel, action, status, error_message)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (report_date, channel, action) DO NOTHING""",
        (operation_id, report_date, channel, action, status, error_message),
    )
    return cursor.rowcount == 1


def claim_delivery_action(connection, *, report_date: date, channel: str, action: str) -> bool:
    """为一次指定日期和渠道的人工操作预占执行权。"""
    return record_delivery_action(
        connection,
        operation_id=None,
        report_date=report_date,
        channel=channel,
        action=action,
        status="running",
    )


def get_delivery_action(connection, *, report_date: date, channel: str, action: str):
    cursor = connection.cursor()
    cursor.execute(
        """SELECT report_date, channel, action, status, external_id, error_message
        FROM ops.platform_delivery_actions
        WHERE report_date = %s AND channel = %s AND action = %s""",
        (report_date, channel, action),
    )
    return cursor.fetchone()


def finish_delivery_action(
    connection,
    *,
    report_date: date,
    channel: str,
    action: str,
    status: str,
    external_id: str | None = None,
    error_message: str | None = None,
) -> None:
    if status not in {"sent", "created", "failed", "uncertain"}:
        raise ValueError("invalid delivery action status")
    connection.cursor().execute(
        """UPDATE ops.platform_delivery_actions
        SET status = %s, external_id = %s, error_message = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE report_date = %s AND channel = %s AND action = %s
          AND status = 'running'""",
        (status, external_id, error_message, report_date, channel, action),
    )


def list_recent_runs(connection, *, limit: int = 20):
    cursor = connection.cursor()
    cursor.execute(
        """SELECT id, kind, report_date, status, error_message, started_at, finished_at
        FROM ops.platform_operation_runs ORDER BY id DESC LIMIT %s""",
        (limit,),
    )
    return cursor.fetchall()


def list_recent_checks(connection, *, limit: int = 50) -> tuple[CheckResult, ...]:
    cursor = connection.cursor()
    cursor.execute(
        """SELECT check_name, status, summary, error_message
        FROM ops.platform_check_results ORDER BY id DESC LIMIT %s""",
        (limit,),
    )
    return tuple(CheckResult(*row) for row in cursor.fetchall())
