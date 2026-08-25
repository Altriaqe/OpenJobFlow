from datetime import date

import pytest

from jobflow.db.snapshots import (
    get_delivery,
    get_deliveries_for_update,
    get_snapshot,
    insert_snapshot,
    list_dated_snapshots,
    list_snapshot_items,
    record_photo_failure,
    record_photo_sending,
    record_photo_sent,
    record_recovered_photo_sent,
    record_text_failure,
    record_text_sending,
    record_text_sent,
)
from jobflow.models.job import JobRecord
from jobflow.models.snapshot import SnapshotMetadata


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.executed.append((sql, params))

    def fetchone(self) -> tuple[int]:
        return (17,)


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


def metadata() -> SnapshotMetadata:
    return SnapshotMetadata(
        snapshot_date=date(2026, 8, 18),
        search_keyword="AI Agent",
        cities=("上海", "北京", "杭州", "深圳"),
        pages_per_city=3,
        details_included=False,
    )


def job() -> JobRecord:
    return JobRecord(
        source="boss_zhipin",
        external_id="job-001",
        title="AI Agent 工程师",
        company="示例公司",
        city="上海",
        detail_url="https://example.com/job-001",
        salary_text="20-30K",
        salary_min=20,
        salary_max=30,
        salary_unit="K_PER_MONTH",
        skills=["Python", "RAG"],
    )


def test_insert_snapshot_writes_header_items_and_delivery() -> None:
    connection = FakeConnection()

    snapshot_id = insert_snapshot(
        connection,
        batch_id=42,
        metadata=metadata(),
        jobs=[job()],
    )

    assert snapshot_id == 17
    assert len(connection.cursor_instance.executed) == 3

    header_sql, header_params = connection.cursor_instance.executed[0]
    assert "INSERT INTO core.job_snapshots" in header_sql
    assert header_params == (
        date(2026, 8, 18),
        "AI Agent",
        42,
        4,
        ["上海", "北京", "杭州", "深圳"],
        3,
        False,
    )

    item_sql, item_params = connection.cursor_instance.executed[1]
    assert "INSERT INTO core.job_snapshot_items" in item_sql
    assert item_params[0:6] == (
        17,
        "boss_zhipin",
        "job-001",
        "AI Agent 工程师",
        "示例公司",
        "上海",
    )
    assert item_params[-1] == ["Python", "RAG"]

    delivery_sql, delivery_params = connection.cursor_instance.executed[2]
    assert "INSERT INTO ops.report_deliveries" in delivery_sql
    assert delivery_params == (17,)


def test_insert_snapshot_rejects_empty_jobs() -> None:
    connection = FakeConnection()

    with pytest.raises(ValueError, match="must not be empty"):
        insert_snapshot(
            connection,
            batch_id=42,
            metadata=metadata(),
            jobs=[],
        )

    assert connection.cursor_instance.executed == []


class ReadCursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.executed.append((sql, params))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class ReadConnection:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.cursor_instance = ReadCursor(rows)

    def cursor(self) -> ReadCursor:
        return self.cursor_instance


def test_get_snapshot_filters_by_exact_natural_date_and_keyword() -> None:
    connection = ReadConnection(
        [(17, date(2026, 8, 18), "AI Agent", 42, 4, list(metadata().cities), 3, False)]
    )

    result = get_snapshot(
        connection,
        snapshot_date=date(2026, 8, 18),
        search_keyword="AI Agent",
    )

    sql, params = connection.cursor_instance.executed[0]
    assert "snapshot_date = %s" in sql
    assert "search_keyword = %s" in sql
    assert params == (date(2026, 8, 18), "AI Agent")
    assert result is not None
    assert result.id == 17
    assert result.scope_key == metadata().scope_key


def test_get_snapshot_returns_none_when_natural_date_is_missing() -> None:
    assert (
        get_snapshot(
            ReadConnection([]),
            snapshot_date=date(2026, 8, 17),
            search_keyword="AI Agent",
        )
        is None
    )


def test_list_snapshot_items_maps_skills_to_tuple() -> None:
    connection = ReadConnection(
        [("boss_zhipin", "job-1", "算法工程师", "示例公司", "上海", 20, 30, "K_PER_MONTH", ["Python", "RAG"])]
    )

    result = list_snapshot_items(connection, 17)

    assert result[0].identity == ("boss_zhipin", "job-1")
    assert result[0].skills == ("Python", "RAG")


def test_list_dated_snapshots_groups_only_dates_returned_by_database() -> None:
    connection = ReadConnection(
        [
            (date(2026, 8, 17), "boss_zhipin", "a", "岗位 A", "公司", "上海", 20, 30, "K_PER_MONTH", []),
            (date(2026, 8, 18), "boss_zhipin", "b", "岗位 B", "公司", "北京", 20, 30, "K_PER_MONTH", ["Python"]),
        ]
    )

    result = list_dated_snapshots(
        connection,
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 18),
        search_keyword="AI Agent",
    )

    assert [day.snapshot_date for day in result] == [date(2026, 8, 17), date(2026, 8, 18)]


def test_get_delivery_maps_nullable_message_ids() -> None:
    result = get_delivery(ReadConnection([(17, "partial_failed", 1001, None, 1, 3, "timeout")]), 17)

    assert result is not None
    assert result.status == "partial_failed"
    assert result.photo_message_id is None
    assert result.photo_attempts == 3


def test_get_deliveries_for_update_locks_exact_group() -> None:
    connection = ReadConnection(
        [
            (11, "pending", None, None, 0, 0, None),
            (12, "pending", None, None, 0, 0, None),
        ]
    )

    result = get_deliveries_for_update(connection, [12, 11])

    sql, params = connection.cursor_instance.executed[0]
    assert "FOR UPDATE" in sql
    assert "ORDER BY snapshot_id" in sql
    assert params == ([11, 12],)
    assert [item.snapshot_id for item in result] == [11, 12]


def test_get_deliveries_for_update_rejects_incomplete_group() -> None:
    connection = ReadConnection([(11, "pending", None, None, 0, 0, None)])

    with pytest.raises(ValueError, match="incomplete"):
        get_deliveries_for_update(connection, [11, 12])


@pytest.mark.parametrize(
    ("transition", "expected_status", "attempt_fragment"),
    [
        (record_text_sending, "text_sending", "text_attempts = text_attempts + 1"),
        (record_photo_sending, "photo_sending", "photo_attempts = photo_attempts + 1"),
    ],
)
def test_sending_transition_preclaims_before_network(
    transition, expected_status: str, attempt_fragment: str
) -> None:
    connection = ReadConnection([])

    transition(connection, 17)

    sql, params = connection.cursor_instance.executed[0]
    assert attempt_fragment in " ".join(sql.split())
    assert params == (expected_status, None, 17)


@pytest.mark.parametrize(
    ("text_receipt_known", "expected_status"),
    [(False, "completed_text_uncertain"), (True, "completed")],
)
def test_recovered_photo_records_honest_final_state(
    text_receipt_known: bool, expected_status: str
) -> None:
    connection = ReadConnection([])

    record_recovered_photo_sent(
        connection,
        17,
        message_id=202,
        attempts=1,
        text_receipt_known=text_receipt_known,
    )

    sql, params = connection.cursor_instance.executed[0]
    assert "photo_message_id" in sql
    assert params == (expected_status, 202, 1, None, 17)


@pytest.mark.parametrize(
    ("transition", "expected_status", "expected_fragment", "expected_params"),
    [
        (record_text_sent, "text_sent", "text_message_id", ("text_sent", 101, 2, None, 17)),
        (record_photo_sent, "completed", "photo_message_id", ("completed", 101, 2, None, 17)),
    ],
)
def test_successful_delivery_transitions(
    transition, expected_status: str, expected_fragment: str, expected_params: tuple[object, ...]
) -> None:
    connection = ReadConnection([])

    transition(connection, 17, 101, 2)

    sql, params = connection.cursor_instance.executed[0]
    assert "status = %s" in sql
    assert expected_fragment in sql
    assert params == expected_params
    assert params[0] == expected_status


@pytest.mark.parametrize(
    ("transition", "expected_status", "expected_attempt_column"),
    [
        (record_text_failure, "failed", "text_attempts"),
        (record_photo_failure, "partial_failed", "photo_attempts"),
    ],
)
def test_failed_delivery_transitions_do_not_set_message_id(
    transition, expected_status: str, expected_attempt_column: str
) -> None:
    connection = ReadConnection([])

    transition(connection, 17, "timeout", 3)

    sql, params = connection.cursor_instance.executed[0]
    assert "message_id" not in sql
    assert expected_attempt_column in sql
    assert params == (expected_status, 3, "timeout", 17)


def test_delivery_transition_rejects_invalid_message_id_before_sql() -> None:
    connection = ReadConnection([])

    with pytest.raises(ValueError, match="positive"):
        record_text_sent(connection, 17, 0, 1)

    assert connection.cursor_instance.executed == []
