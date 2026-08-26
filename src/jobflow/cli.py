"""命令行入口：读取一个快照文件并交给 ETL Worker 处理。"""

import argparse
from datetime import date
from pathlib import Path
import sys

from jobflow.adapters.boss import SnapshotError
from jobflow.models.snapshot import SnapshotMetadata
from jobflow.workers.etl import run_boss_snapshot


def parse_cities(value: str) -> tuple[str, ...]:
    cities = tuple(part.strip() for part in value.split(","))
    if not cities or any(not city for city in cities):
        raise argparse.ArgumentTypeError("cities must be non-empty")
    return cities


def build_parser() -> argparse.ArgumentParser:
    """定义快照路径和可选的每日快照元数据参数。"""
    parser = argparse.ArgumentParser(description="Process one JobFlow BOSS snapshot")
    parser.add_argument("snapshot", type=Path, help="path to the BOSS snapshot JSON file")
    parser.add_argument("--snapshot-date", type=date.fromisoformat)
    parser.add_argument("--search-keyword")
    parser.add_argument("--cities", type=parse_cities)
    parser.add_argument("--pages-per-city", type=int)
    parser.add_argument("--detail-mode", choices=("no-detail", "detail"))
    return parser


def build_snapshot_metadata(args: argparse.Namespace) -> SnapshotMetadata | None:
    values = (
        args.snapshot_date,
        args.search_keyword,
        args.cities,
        args.pages_per_city,
        args.detail_mode,
    )
    if not any(value is not None for value in values):
        return None
    if not all(value is not None for value in values):
        raise ValueError("daily snapshot metadata options must be provided together")
    return SnapshotMetadata(
        snapshot_date=args.snapshot_date,
        search_keyword=args.search_keyword,
        cities=args.cities,
        pages_per_city=args.pages_per_city,
        details_included=args.detail_mode == "detail",
    )


def main(argv: list[str] | None = None) -> int:
    """解析参数、执行 ETL，并把用户可读错误转换为非零退出码。"""
    args = build_parser().parse_args(argv)
    try:
        metadata = build_snapshot_metadata(args)
        run_boss_snapshot(args.snapshot, metadata=metadata)
    except SnapshotError as exc:
        print(f"ETL failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ETL failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    print(f"ETL completed: {args.snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
