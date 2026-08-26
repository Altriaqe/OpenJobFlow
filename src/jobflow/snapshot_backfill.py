"""历史快照基线回填入口：只处理经过审核、口径明确的批次。"""

import argparse
from dataclasses import dataclass
from datetime import date
import sys

from jobflow.adapters.boss import map_boss_jobs
from jobflow.db.connection import connect_postgres
from jobflow.db.snapshots import get_snapshot, insert_snapshot
from jobflow.models.snapshot import SnapshotMetadata


@dataclass(frozen=True)
class VerifiedBackfillRequest:
    batch_id: int
    snapshot_date: date
    search_keyword: str
    cities: tuple[str, ...]
    pages_per_city: int
    details_included: bool


@dataclass(frozen=True)
class BatchCandidate:
    batch_id: int
    status: str
    row_count: int
    raw_jobs: tuple[dict[str, str], ...]


def _parse_cities(value: str) -> tuple[str, ...]:
    cities = tuple(part.strip() for part in value.split(","))
    if not cities or any(not city for city in cities) or len(set(cities)) != len(cities):
        raise argparse.ArgumentTypeError("cities must be non-empty and unique")
    return cities


def audit_batches(connection, *, start_date: date, end_date: date) -> tuple[tuple[object, ...], ...]:
    """列出日期范围内可供人工核验的批次，不自动修改数据。"""
    """只读列出可能用于人工核验的历史批次，不读取完整岗位内容。"""

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            b.id,
            b.status,
            b.started_at::date,
            b.row_count,
            COUNT(r.id) AS raw_count,
            COUNT(DISTINCT r.payload ->> 'location') AS raw_location_count
        FROM ops.batches AS b
        LEFT JOIN raw.job_records AS r ON r.batch_id = b.id
        WHERE b.started_at::date BETWEEN %s AND %s
        GROUP BY b.id, b.status, b.started_at::date, b.row_count
        ORDER BY b.started_at::date, b.id
        """,
        (start_date, end_date),
    )
    return tuple(cursor.fetchall())


def _load_batch_candidate(connection, batch_id: int) -> BatchCandidate | None:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT b.id, b.status, b.row_count, r.source, r.external_id, r.payload
        FROM ops.batches AS b
        LEFT JOIN raw.job_records AS r ON r.batch_id = b.id
        WHERE b.id = %s
        ORDER BY r.id
        """,
        (batch_id,),
    )
    rows = cursor.fetchall()
    if not rows:
        return None
    raw_jobs: list[dict[str, str]] = []
    for row in rows:
        source, external_id, payload = row[3], row[4], row[5]
        if source is None or external_id is None or payload is None:
            continue
        if source != "boss_zhipin" or not isinstance(payload, dict):
            raise ValueError("batch contains unsupported raw source or payload")
        if payload.get("job_id") != external_id:
            raise ValueError("raw external_id does not match payload job_id")
        raw_jobs.append(payload)
    return BatchCandidate(
        batch_id=rows[0][0],
        status=rows[0][1],
        row_count=rows[0][2],
        raw_jobs=tuple(raw_jobs),
    )


def backfill_verified_batch(connection, request: VerifiedBackfillRequest) -> int:
    """将已确认批次写入快照表，保持原批次和采集口径不变。"""
    """将人工确认口径的一个成功批次回填为快照；本函数不会发送消息。"""

    metadata = SnapshotMetadata(
        snapshot_date=request.snapshot_date,
        search_keyword=request.search_keyword,
        cities=request.cities,
        pages_per_city=request.pages_per_city,
        details_included=request.details_included,
    )
    existing = get_snapshot(
        connection,
        snapshot_date=request.snapshot_date,
        search_keyword=request.search_keyword,
    )
    if existing is not None:
        if existing.batch_id != request.batch_id:
            raise ValueError("snapshot date and keyword already belong to another batch")
        if existing.scope_key != metadata.scope_key:
            raise ValueError("existing snapshot scope does not match requested scope")
        return existing.id

    candidate = _load_batch_candidate(connection, request.batch_id)
    if candidate is None:
        raise ValueError("batch does not exist")
    if candidate.status != "succeeded":
        raise ValueError("batch must be succeeded")
    if candidate.row_count != len(candidate.raw_jobs):
        raise ValueError("batch row count does not match raw row count")
    if not candidate.raw_jobs:
        raise ValueError("batch must be non-empty")

    jobs = map_boss_jobs(list(candidate.raw_jobs))
    declared_cities = set(request.cities)
    unknown_cities = sorted({job.city for job in jobs if job.city not in declared_cities})
    if unknown_cities:
        raise ValueError(f"mapped jobs contain undeclared city: {unknown_cities!r}")
    identities = [job.source + "\0" + job.external_id for job in jobs]
    if len(identities) != len(set(identities)):
        raise ValueError("batch contains duplicate job identity")

    snapshot_id = insert_snapshot(
        connection,
        batch_id=request.batch_id,
        metadata=metadata,
        jobs=jobs,
    )
    connection.commit()
    return snapshot_id


def build_parser() -> argparse.ArgumentParser:
    """构造审计和回填命令行参数。"""
    parser = argparse.ArgumentParser(description="Audit and explicitly backfill JobFlow snapshots")
    commands = parser.add_subparsers(dest="command", required=True)

    audit = commands.add_parser("audit", help="list non-secret historical batch evidence")
    audit.add_argument("--start-date", type=date.fromisoformat, required=True)
    audit.add_argument("--end-date", type=date.fromisoformat, required=True)

    backfill = commands.add_parser("backfill", help="backfill one manually verified batch")
    backfill.add_argument("--batch-id", type=int, required=True)
    backfill.add_argument("--snapshot-date", type=date.fromisoformat, required=True)
    backfill.add_argument("--search-keyword", required=True)
    backfill.add_argument("--cities", type=_parse_cities, required=True)
    backfill.add_argument("--pages-per-city", type=int, required=True)
    backfill.add_argument("--detail-mode", choices=("no-detail", "detail"), required=True)
    backfill.add_argument("--confirm-scope", action="store_true")
    return parser


def _print_audit(rows: tuple[tuple[object, ...], ...]) -> None:
    print("batch_id\tdate\tstatus\trow_count\traw_count\tlocation_count")
    for batch_id, status, batch_date, row_count, raw_count, location_count in rows:
        print(
            f"{batch_id}\t{batch_date}\t{status}\t{row_count}\t{raw_count}\t{location_count}"
        )


def main(argv: list[str] | None = None) -> int:
    """执行审计或人工确认后的回填，并返回 CLI 退出码。"""
    args = build_parser().parse_args(argv)
    if args.command == "backfill" and not args.confirm_scope:
        print("backfill requires --confirm-scope after manual verification", file=sys.stderr)
        return 2

    connection = connect_postgres()
    try:
        if args.command == "audit":
            if args.end_date < args.start_date:
                raise ValueError("end date must not be before start date")
            _print_audit(
                audit_batches(
                    connection,
                    start_date=args.start_date,
                    end_date=args.end_date,
                )
            )
            connection.rollback()
            return 0

        request = VerifiedBackfillRequest(
            batch_id=args.batch_id,
            snapshot_date=args.snapshot_date,
            search_keyword=args.search_keyword,
            cities=args.cities,
            pages_per_city=args.pages_per_city,
            details_included=args.detail_mode == "detail",
        )
        snapshot_id = backfill_verified_batch(connection, request)
        print(f"snapshot backfill completed: snapshot_id={snapshot_id}")
        return 0
    except Exception as exc:
        connection.rollback()
        print(f"snapshot backfill failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
