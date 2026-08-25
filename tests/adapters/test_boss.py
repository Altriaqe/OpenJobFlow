import json
from pathlib import Path

import pytest

from jobflow.adapters.boss import (
    SnapshotError,
    load_boss_jobs,
    map_boss_job,
    map_boss_jobs,
    parse_salary,
    parse_skills,
)
from jobflow.models.job import JobRecord


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("15-25K", (15, 25, "K_PER_MONTH", None)),
        ("15-25K·14薪", (15, 25, "K_PER_MONTH", 14)),
        ("5000-7000元/月", (5, 7, "K_PER_MONTH", None)),
        ("3500-5500元/月", (3500, 5500, "CNY_PER_MONTH", None)),
        ("200-300元/天", (200, 300, "CNY_PER_DAY", None)),
        ("50-60元/时", (50, 60, "CNY_PER_HOUR", None)),
    ],
)
def test_parse_salary_returns_normalized_values(value, expected) -> None:
    salary = parse_salary(value)

    assert (salary.minimum, salary.maximum, salary.unit, salary.months) == expected
    assert salary.source_text == value


def test_parse_salary_accepts_negotiable_salary() -> None:
    salary = parse_salary("面议")

    assert salary.source_text == "面议"
    assert salary.minimum is None
    assert salary.maximum is None
    assert salary.unit is None
    assert salary.months is None


@pytest.mark.parametrize(
    "value",
    [
        "0-10K",
        "30-20K",
        "15-25K·0薪",
        "0-10元/时",
        "60-50元/时",
        "5500-3500元/月",
    ],
)
def test_parse_salary_rejects_invalid_values(value) -> None:
    with pytest.raises(SnapshotError, match="薪资数值不合法"):
        parse_salary(value)


def test_parse_skills_splits_strips_and_deduplicates_in_order() -> None:
    assert parse_skills("Python | SQL | Python |  ") == ["Python", "SQL"]


def test_parse_skills_returns_empty_list_for_blank_value() -> None:
    assert parse_skills("   ") == []


def test_map_boss_job_returns_job_record() -> None:
    raw_job = {
        "job_id": "job-001",
        "title": "Python 数据开发工程师",
        "boss_name": "示例科技",
        "location": "上海·浦东新区·张江",
        "job_link": "https://www.zhipin.com/job_detail/job-001.html",
        "salary": "15-25K·14薪",
        "skills": "Python | SQL | Python",
    }
    expected = JobRecord(
        source="boss_zhipin",
        external_id="job-001",
        title="Python 数据开发工程师",
        company="示例科技",
        city="上海",
        detail_url="https://www.zhipin.com/job_detail/job-001.html",
        salary_text="15-25K·14薪",
        salary_min=15,
        salary_max=25,
        salary_unit="K_PER_MONTH",
        salary_months=14,
        skills=["Python", "SQL"],
    )

    actual = map_boss_job(raw_job)
    assert actual == expected


def test_map_boss_job_preserves_negotiable_salary_as_unknown() -> None:
    raw_job = {
        "job_id": "job-negotiable",
        "title": "数据分析师",
        "boss_name": "示例科技",
        "location": "深圳·南山区",
        "job_link": "https://www.zhipin.com/job_detail/job-negotiable.html",
        "salary": "面议",
        "skills": "SQL",
    }

    job = map_boss_job(raw_job)

    assert job.salary_text == "面议"
    assert job.salary_min is None
    assert job.salary_max is None
    assert job.salary_unit is None
    assert job.salary_months is None


def test_load_boss_jobs_returns_jobs_list(tmp_path: Path) -> None:
    raw_jobs = [
        {
            "job_id": "job-001",
            "title": "Python 数据开发工程师",
            "boss_name": "示例科技",
            "location": "上海·浦东新区·张江",
            "job_link": "https://www.zhipin.com/job_detail/job-001.html",
            "salary": "15-25K",
            "skills": "Python | SQL",
        },
    ]

    snapshot_data = {
        "jobs": raw_jobs,
    }
    snapshot_path = tmp_path / "boss_jobs.json"
    snapshot_path.write_text(
        json.dumps(snapshot_data, ensure_ascii=False),
        encoding="utf-8",
    )

    actual = load_boss_jobs(snapshot_path)
    assert actual == raw_jobs


def test_map_boss_jobs_returns_job_records() -> None:
    raw_jobs = [
        {
            "job_id": "job-001",
            "title": "Python 数据开发工程师",
            "boss_name": "示例科技",
            "location": "上海·浦东新区·张江",
            "job_link": "https://www.zhipin.com/job_detail/job-001.html",
            "salary": "15-25K",
            "skills": "Python | SQL",
        },
        {
            "job_id": "job-002",
            "title": "Java 后端开发工程师",
            "boss_name": "示例科技",
            "location": "北京·海淀区·中关村",
            "job_link": "https://www.zhipin.com/job_detail/job-002.html",
            "salary": "20-30K",
            "skills": "Java | SQL",
        },
    ]

    expected = [
        JobRecord(
            source="boss_zhipin",
            external_id="job-001",
            title="Python 数据开发工程师",
            company="示例科技",
            city="上海",
            detail_url="https://www.zhipin.com/job_detail/job-001.html",
            salary_text="15-25K",
            salary_min=15,
            salary_max=25,
            salary_unit="K_PER_MONTH",
            skills=["Python", "SQL"],
        ),
        JobRecord(
            source="boss_zhipin",
            external_id="job-002",
            title="Java 后端开发工程师",
            company="示例科技",
            city="北京",
            detail_url="https://www.zhipin.com/job_detail/job-002.html",
            salary_text="20-30K",
            salary_min=20,
            salary_max=30,
            salary_unit="K_PER_MONTH",
            skills=["Java", "SQL"],
        ),
    ]

    actual = map_boss_jobs(raw_jobs)
    assert actual == expected


def test_load_boss_jobs_raises_snapshot_error_when_file_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "non_existent.json"
    with pytest.raises(SnapshotError) as exc_info:
        load_boss_jobs(missing_path)

    assert str(missing_path) in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, FileNotFoundError)


def test_load_boss_jobs_raises_snapshot_error_when_json_invalid(tmp_path: Path) -> None:
    invalid_json_path = tmp_path / "invalid.json"
    invalid_json_path.write_text("invalid json content", encoding="utf-8")

    with pytest.raises(SnapshotError) as exc_info:
        load_boss_jobs(invalid_json_path)

    assert str(invalid_json_path) in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


def test_load_boss_jobs_raises_snapshot_error_when_jobs_missing(
    tmp_path: Path,
) -> None:
    missing_jobs_path = tmp_path / "missing_jobs.json"
    snapshot_data = {}
    missing_jobs_path.write_text(json.dumps(snapshot_data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(SnapshotError) as exc_info:
        load_boss_jobs(missing_jobs_path)

    assert str(missing_jobs_path) in str(exc_info.value)


def test_load_boss_jobs_raises_snapshot_error_when_jobs_not_list(
    tmp_path: Path,
) -> None:
    not_list_path = tmp_path / "not_list.json"
    snapshot_data = {
        "jobs": {},
    }

    not_list_path.write_text(json.dumps(snapshot_data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SnapshotError) as exc_info:
        load_boss_jobs(not_list_path)

    assert str(not_list_path) in str(exc_info.value)


def test_load_boss_jobs_raises_snapshot_error_when_job_not_dict(
    tmp_path: Path,
) -> None:
    snapshot_path = tmp_path / "job_not_dict.json"
    snapshot_data = {
        "jobs": ["hello world"],
    }

    snapshot_path.write_text(json.dumps(snapshot_data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SnapshotError) as exc_info:
        load_boss_jobs(snapshot_path)

    assert str(snapshot_path) in str(exc_info.value)
    assert "1" in str(exc_info.value)


def test_load_boss_jobs_raises_snapshot_error_when_required_field_missing(
    tmp_path: Path,
) -> None:
    snapshot_path = tmp_path / "missing_field.json"
    snapshot_data = {
        "jobs": [
            {
                "title": "Python 数据开发工程师",
                "boss_name": "示例科技",
                "location": "上海·浦东新区·张江",
                "job_link": "https://www.zhipin.com/job_detail/job-001.html",
                "salary": "15-25K",
                "skills": "Python | SQL",
            },
        ],
    }

    snapshot_path.write_text(json.dumps(snapshot_data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SnapshotError) as exc_info:
        load_boss_jobs(snapshot_path)

    message = str(exc_info.value)

    assert str(snapshot_path) in message
    assert "job_id" in message
    assert "1" in message


def test_load_boss_jobs_raises_snapshot_error_when_required_field_empty(
    tmp_path: Path,
) -> None:
    snapshot_path = tmp_path / "empty_field.json"
    snapshot_data = {
        "jobs": [
            {
                "job_id": "job-001",
                "title": "",
                "boss_name": "示例科技",
                "location": "上海·浦东新区·张江",
                "job_link": "https://www.zhipin.com/job_detail/job-001.html",
                "salary": "15-25K",
                "skills": "Python | SQL",
            },
        ],
    }

    snapshot_path.write_text(json.dumps(snapshot_data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SnapshotError) as exc_info:
        load_boss_jobs(snapshot_path)

    message = str(exc_info.value)

    assert str(snapshot_path) in message
    assert "title" in message
    assert "1" in message


def test_load_boss_jobs_raises_snapshot_error_when_required_field_not_string(
    tmp_path: Path,
) -> None:
    snapshot_path = tmp_path / "non_string_field.json"
    snapshot_data = {
        "jobs": [
            {
                "job_id": 123,
                "title": "Python 数据开发工程师",
                "boss_name": "示例科技",
                "location": "上海·浦东新区·张江",
                "job_link": "https://www.zhipin.com/job_detail/job-001.html",
                "salary": "15-25K",
                "skills": "Python | SQL",
            },
        ],
    }

    snapshot_path.write_text(json.dumps(snapshot_data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SnapshotError) as exc_info:
        load_boss_jobs(snapshot_path)

    message = str(exc_info.value)

    assert str(snapshot_path) in message
    assert "job_id" in message
    assert "1" in message


def test_load_boss_jobs_raises_snapshot_error_when_required_field_blank(
    tmp_path: Path,
) -> None:
    snapshot_path = tmp_path / "blank_field.json"
    snapshot_data = {
        "jobs": [
            {
                "job_id": "job-001",
                "title": "  ",
                "boss_name": "示例科技",
                "location": "上海·浦东新区·张江",
                "job_link": "https://www.zhipin.com/job_detail/job-001.html",
                "salary": "15-25K",
                "skills": "Python | SQL",
            },
        ],
    }

    snapshot_path.write_text(json.dumps(snapshot_data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SnapshotError) as exc_info:
        load_boss_jobs(snapshot_path)

    message = str(exc_info.value)

    assert str(snapshot_path) in message
    assert "title" in message
    assert "1" in message
