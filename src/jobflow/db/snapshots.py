"""每日快照与 Telegram 投递状态持久化，负责幂等认领和结果记录。"""

from datetime import date

from jobflow.models.job import JobRecord
from jobflow.models.snapshot import (
    DatedSnapshot,
    NewJobPosting,
    ReportDelivery,
    SnapshotHeader,
    SnapshotItem,
    SnapshotMetadata,
)


def insert_snapshot(
    connection,
    *,
    batch_id: int,
    metadata: SnapshotMetadata,
    jobs: list[JobRecord],
) -> int:
    """写入一份带采集口径的不可变快照及其岗位观察值。"""
    """写入一份不可变的每日岗位快照，并创建待发送状态。"""

    if not jobs:
        raise ValueError("snapshot jobs must not be empty")

    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO core.job_snapshots (
            snapshot_date,
            search_keyword,
            batch_id,
            city_count,
            cities,
            pages_per_city,
            details_included
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            metadata.snapshot_date,
            metadata.search_keyword,
            batch_id,
            metadata.city_count,
            list(metadata.cities),
            metadata.pages_per_city,
            metadata.details_included,
        ),
    )
    snapshot_id = cursor.fetchone()[0]

    item_sql = """
        INSERT INTO core.job_snapshot_items (
            snapshot_id,
            source,
            external_id,
            title,
            company,
            city,
            salary_text,
            salary_min,
            salary_max,
            salary_unit,
            salary_months,
            skills
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    for job in jobs:
        cursor.execute(
            item_sql,
            (
                snapshot_id,
                job.source,
                job.external_id,
                job.title,
                job.company,
                job.city,
                job.salary_text,
                job.salary_min,
                job.salary_max,
                job.salary_unit,
                job.salary_months,
                job.skills,
            ),
        )

    cursor.execute(
        "INSERT INTO ops.report_deliveries (snapshot_id) VALUES (%s)",
        (snapshot_id,),
    )
    return snapshot_id


def get_snapshot(
    connection,
    *,
    snapshot_date: date,
    search_keyword: str,
) -> SnapshotHeader | None:
    """按日期、关键词和采集范围读取快照头，供日报比较使用。"""
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            id, snapshot_date, search_keyword, batch_id, city_count,
            cities, pages_per_city, details_included
        FROM core.job_snapshots
        WHERE snapshot_date = %s
          AND search_keyword = %s
          AND status = 'succeeded'
        """,
        (snapshot_date, search_keyword),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return SnapshotHeader(
        id=row[0],
        snapshot_date=row[1],
        search_keyword=row[2],
        batch_id=row[3],
        city_count=row[4],
        cities=tuple(row[5]),
        pages_per_city=row[6],
        details_included=row[7],
    )


def _snapshot_item_from_row(row: tuple[object, ...], offset: int = 0) -> SnapshotItem:
    return SnapshotItem(
        source=row[offset],
        external_id=row[offset + 1],
        title=row[offset + 2],
        company=row[offset + 3],
        city=row[offset + 4],
        salary_min=row[offset + 5],
        salary_max=row[offset + 6],
        salary_unit=row[offset + 7],
        skills=tuple(row[offset + 8] or ()),
    )


def list_snapshot_items(connection, snapshot_id: int) -> tuple[SnapshotItem, ...]:
    """读取快照岗位观察值；结果按稳定身份排序以保证报告确定性。"""
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            source, external_id, title, company, city,
            salary_min, salary_max, salary_unit, skills
        FROM core.job_snapshot_items
        WHERE snapshot_id = %s
        ORDER BY source, external_id
        """,
        (snapshot_id,),
    )
    return tuple(_snapshot_item_from_row(row) for row in cursor.fetchall())


def list_dated_snapshots(
    connection,
    *,
    start_date: date,
    end_date: date,
    search_keyword: str,
) -> tuple[DatedSnapshot, ...]:
    """读取日期范围内快照，为日环比和周环比提供输入。"""
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            s.snapshot_date,
            i.source, i.external_id, i.title, i.company, i.city,
            i.salary_min, i.salary_max, i.salary_unit, i.skills
        FROM core.job_snapshots AS s
        JOIN core.job_snapshot_items AS i ON i.snapshot_id = s.id
        WHERE s.snapshot_date BETWEEN %s AND %s
          AND s.search_keyword = %s
          AND s.status = 'succeeded'
        ORDER BY s.snapshot_date, i.source, i.external_id
        """,
        (start_date, end_date, search_keyword),
    )
    grouped: dict[date, list[SnapshotItem]] = {}
    for row in cursor.fetchall():
        grouped.setdefault(row[0], []).append(_snapshot_item_from_row(row, offset=1))
    return tuple(
        DatedSnapshot(snapshot_date=snapshot_date, items=tuple(items))
        for snapshot_date, items in grouped.items()
    )


def list_new_job_postings(
    connection,
    *,
    current_snapshot_id: int,
    previous_snapshot_id: int,
    keyword: str,
) -> tuple[NewJobPosting, ...]:
    """返回当前快照中首次出现的岗位，并尽可能补充原平台详情链接。"""
    if current_snapshot_id <= 0 or previous_snapshot_id <= 0:
        raise ValueError("snapshot ids must be positive")
    if current_snapshot_id == previous_snapshot_id:
        raise ValueError("snapshot ids must be distinct")
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise ValueError("keyword must not be empty")

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            current.source,
            current.external_id,
            current.title,
            current.company,
            current.city,
            current.salary_text,
            current.salary_min,
            current.salary_max,
            current.salary_unit,
            current.salary_months,
            current.skills,
            jobs.detail_url
        FROM core.job_snapshot_items AS current
        LEFT JOIN core.job_snapshot_items AS previous
          ON previous.snapshot_id = %s
         AND previous.source = current.source
         AND previous.external_id = current.external_id
        LEFT JOIN core.jobs AS jobs
          ON jobs.source = current.source
         AND jobs.external_id = current.external_id
        JOIN core.job_snapshots AS snapshot
          ON snapshot.id = current.snapshot_id
        WHERE current.snapshot_id = %s
          AND snapshot.search_keyword = %s
          AND previous.source IS NULL
        ORDER BY current.city, current.title, current.external_id, current.source
        """,
        (previous_snapshot_id, current_snapshot_id, normalized_keyword),
    )
    return tuple(
        NewJobPosting(
            source=row[0],
            external_id=row[1],
            keyword=normalized_keyword,
            title=row[2],
            company=row[3],
            city=row[4],
            salary_text=row[5],
            salary_min=row[6],
            salary_max=row[7],
            salary_unit=row[8],
            salary_months=row[9],
            skills=tuple(row[10] or ()),
            detail_url=row[11],
        )
        for row in cursor.fetchall()
    )


def get_delivery(connection, snapshot_id: int) -> ReportDelivery | None:
    """读取单份快照的文字/图片投递状态。"""
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            snapshot_id, status, text_message_id, photo_message_id,
            text_attempts, photo_attempts, last_error_type
        FROM ops.report_deliveries
        WHERE snapshot_id = %s
        """,
        (snapshot_id,),
    )
    row = cursor.fetchone()
    return None if row is None else ReportDelivery(*row)


def get_deliveries_for_update(
    connection,
    snapshot_ids: list[int],
) -> tuple[ReportDelivery, ...]:
    """锁定一组投递记录，供调用方在同一事务内预占发送阶段。"""

    normalized = sorted(set(snapshot_ids))
    if not normalized or len(normalized) != len(snapshot_ids):
        raise ValueError("snapshot_ids must be non-empty and unique")

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            snapshot_id, status, text_message_id, photo_message_id,
            text_attempts, photo_attempts, last_error_type
        FROM ops.report_deliveries
        WHERE snapshot_id = ANY(%s)
        ORDER BY snapshot_id
        FOR UPDATE
        """,
        (normalized,),
    )
    deliveries = tuple(ReportDelivery(*row) for row in cursor.fetchall())
    if [delivery.snapshot_id for delivery in deliveries] != normalized:
        raise ValueError("delivery group is incomplete")
    return deliveries


def _update_delivery(
    connection,
    snapshot_id: int,
    *,
    status: str,
    message_column: str | None,
    message_id: int | None,
    attempts_column: str,
    attempts: int,
    error_type: str | None,
) -> None:
    allowed_message_columns = {"text_message_id", "photo_message_id"}
    allowed_attempt_columns = {"text_attempts", "photo_attempts"}
    if attempts_column not in allowed_attempt_columns:
        raise ValueError("unsupported attempts column")
    if message_column is not None and message_column not in allowed_message_columns:
        raise ValueError("unsupported message column")
    if attempts < 0:
        raise ValueError("attempts must not be negative")
    if message_column is not None and (message_id is None or message_id <= 0):
        raise ValueError("message_id must be positive")

    assignments = [
        "status = %s",
        f"{attempts_column} = %s",
        "last_error_type = %s",
        "updated_at = CURRENT_TIMESTAMP",
    ]
    params: list[object] = [status, attempts, error_type]
    if message_column is not None:
        assignments.insert(1, f"{message_column} = %s")
        params.insert(1, message_id)
    params.append(snapshot_id)

    cursor = connection.cursor()
    cursor.execute(
        f"UPDATE ops.report_deliveries SET {', '.join(assignments)} WHERE snapshot_id = %s",
        tuple(params),
    )


def _record_sending(
    connection,
    snapshot_id: int,
    *,
    status: str,
    stage: str,
) -> None:
    if stage not in {"text", "photo"}:
        raise ValueError("unsupported delivery stage")
    attempts_column = f"{stage}_attempts"
    cursor = connection.cursor()
    cursor.execute(
        f"""
        UPDATE ops.report_deliveries
        SET status = %s,
            {attempts_column} = {attempts_column} + 1,
            last_error_type = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE snapshot_id = %s
        """,
        (status, None, snapshot_id),
    )


def record_text_sending(connection, snapshot_id: int) -> None:
    _record_sending(connection, snapshot_id, status="text_sending", stage="text")


def record_photo_sending(connection, snapshot_id: int) -> None:
    _record_sending(connection, snapshot_id, status="photo_sending", stage="photo")


def record_text_sent(connection, snapshot_id: int, message_id: int, attempts: int) -> None:
    _update_delivery(
        connection,
        snapshot_id,
        status="text_sent",
        message_column="text_message_id",
        message_id=message_id,
        attempts_column="text_attempts",
        attempts=attempts,
        error_type=None,
    )


def record_photo_sent(connection, snapshot_id: int, message_id: int, attempts: int) -> None:
    _update_delivery(
        connection,
        snapshot_id,
        status="completed",
        message_column="photo_message_id",
        message_id=message_id,
        attempts_column="photo_attempts",
        attempts=attempts,
        error_type=None,
    )


def record_text_failure(connection, snapshot_id: int, error_type: str, attempts: int) -> None:
    _update_delivery(
        connection,
        snapshot_id,
        status="failed",
        message_column=None,
        message_id=None,
        attempts_column="text_attempts",
        attempts=attempts,
        error_type=error_type,
    )


def record_photo_failure(connection, snapshot_id: int, error_type: str, attempts: int) -> None:
    _update_delivery(
        connection,
        snapshot_id,
        status="partial_failed",
        message_column=None,
        message_id=None,
        attempts_column="photo_attempts",
        attempts=attempts,
        error_type=error_type,
    )


def record_text_failed(connection, snapshot_id: int, error_type: str, attempts: int) -> None:
    _update_delivery(
        connection,
        snapshot_id,
        status="text_failed",
        message_column=None,
        message_id=None,
        attempts_column="text_attempts",
        attempts=attempts,
        error_type=error_type,
    )


def record_photo_failed(connection, snapshot_id: int, error_type: str, attempts: int) -> None:
    _update_delivery(
        connection,
        snapshot_id,
        status="photo_failed",
        message_column=None,
        message_id=None,
        attempts_column="photo_attempts",
        attempts=attempts,
        error_type=error_type,
    )


def record_text_uncertain(
    connection,
    snapshot_id: int,
    error_type: str,
    attempts: int,
) -> None:
    _update_delivery(
        connection,
        snapshot_id,
        status="text_uncertain",
        message_column=None,
        message_id=None,
        attempts_column="text_attempts",
        attempts=attempts,
        error_type=error_type,
    )


def record_photo_uncertain(
    connection,
    snapshot_id: int,
    error_type: str,
    attempts: int,
) -> None:
    _update_delivery(
        connection,
        snapshot_id,
        status="photo_uncertain",
        message_column=None,
        message_id=None,
        attempts_column="photo_attempts",
        attempts=attempts,
        error_type=error_type,
    )


def record_recovered_photo_sent(
    connection,
    snapshot_id: int,
    *,
    message_id: int,
    attempts: int,
    text_receipt_known: bool,
) -> None:
    _update_delivery(
        connection,
        snapshot_id,
        status="completed" if text_receipt_known else "completed_text_uncertain",
        message_column="photo_message_id",
        message_id=message_id,
        attempts_column="photo_attempts",
        attempts=attempts,
        error_type=None,
    )
