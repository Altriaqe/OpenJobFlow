from datetime import date
from pathlib import Path

import pytest

from jobflow import cli
from jobflow.adapters.boss import SnapshotError
from jobflow.models.snapshot import SnapshotMetadata


def test_main_runs_snapshot_and_reports_success(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(
        cli,
        "run_boss_snapshot",
        lambda path, metadata=None: calls.append((path, metadata)),
    )

    result = cli.main(["snapshot.json"])

    assert result == 0
    assert calls == [(Path("snapshot.json"), None)]
    assert "ETL completed: snapshot.json" in capsys.readouterr().out


def test_main_reports_snapshot_error_without_traceback(monkeypatch, capsys):
    def fail(path, metadata=None):
        raise SnapshotError("missing jobs field")

    monkeypatch.setattr(cli, "run_boss_snapshot", fail)

    result = cli.main(["broken.json"])

    captured = capsys.readouterr()
    assert result == 1
    assert captured.err == "ETL failed: missing jobs field\n"
    assert "Traceback" not in captured.err


def test_main_hides_unexpected_error_details(monkeypatch, capsys):
    def fail(path, metadata=None):
        raise RuntimeError("POSTGRES_PASSWORD=secret")

    monkeypatch.setattr(cli, "run_boss_snapshot", fail)

    result = cli.main(["snapshot.json"])

    captured = capsys.readouterr()
    assert result == 1
    assert captured.err == "ETL failed: RuntimeError\n"
    assert "secret" not in captured.err


def test_main_requires_snapshot_path():
    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2


def test_main_forwards_explicit_snapshot_metadata(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli,
        "run_boss_snapshot",
        lambda path, metadata=None: calls.append((path, metadata)),
    )

    result = cli.main(
        [
            "snapshot.json",
            "--snapshot-date",
            "2026-08-18",
            "--search-keyword",
            "AI Agent",
            "--cities",
            "上海,北京,杭州,深圳",
            "--pages-per-city",
            "3",
            "--detail-mode",
            "no-detail",
        ]
    )

    assert result == 0
    assert calls[0][1] == SnapshotMetadata(
        snapshot_date=date(2026, 8, 18),
        search_keyword="AI Agent",
        cities=("上海", "北京", "杭州", "深圳"),
        pages_per_city=3,
        details_included=False,
    )


def test_main_rejects_partial_snapshot_metadata(capsys):
    result = cli.main(
        [
            "snapshot.json",
            "--snapshot-date",
            "2026-08-18",
        ]
    )

    assert result == 1
    assert capsys.readouterr().err == "ETL failed: ValueError\n"


def test_parser_rejects_blank_city_segment():
    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "snapshot.json",
                "--snapshot-date",
                "2026-08-18",
                "--search-keyword",
                "AI Agent",
                "--cities",
                "上海,,北京",
                "--pages-per-city",
                "3",
                "--detail-mode",
                "no-detail",
            ]
        )

    assert exc_info.value.code == 2
