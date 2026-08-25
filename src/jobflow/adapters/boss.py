import json
import re
from dataclasses import dataclass
from pathlib import Path


from jobflow.models.job import JobRecord


class SnapshotError(Exception):
    """快照读取失败"""


@dataclass(frozen=True)
class Salary:
    source_text: str
    minimum: int | None
    maximum: int | None
    unit: str | None
    months: int | None


MONTHLY_SALARY_PATTERN = re.compile(r"^(\d+)-(\d+)K(?:·(\d+)薪)?$")
MONTHLY_CNY_SALARY_PATTERN = re.compile(r"^(\d+)-(\d+)元/月$")
DAILY_SALARY_PATTERN = re.compile(r"^(\d+)-(\d+)元/天$")
HOURLY_SALARY_PATTERN = re.compile(r"^(\d+)-(\d+)元/时$")


def parse_salary(value: str) -> Salary:
    """将 BOSS 薪资原文解析为统一薪资结构。"""
    if value == "面议":
        return Salary(
            source_text=value,
            minimum=None,
            maximum=None,
            unit=None,
            months=None,
        )

    monthly_match = MONTHLY_SALARY_PATTERN.fullmatch(value)
    if monthly_match:
        minimum, maximum, months = monthly_match.groups()
        minimum_value = int(minimum)
        maximum_value = int(maximum)
        months_value = int(months) if months is not None else None
        _validate_salary_values(value, minimum_value, maximum_value, months_value)
        return Salary(
            source_text=value,
            minimum=minimum_value,
            maximum=maximum_value,
            unit="K_PER_MONTH",
            months=months_value,
        )

    monthly_cny_match = MONTHLY_CNY_SALARY_PATTERN.fullmatch(value)
    if monthly_cny_match:
        minimum_cny, maximum_cny = (int(item) for item in monthly_cny_match.groups())
        _validate_salary_values(value, minimum_cny, maximum_cny, None)
        if minimum_cny % 1000 == 0 and maximum_cny % 1000 == 0:
            return Salary(
                source_text=value,
                minimum=minimum_cny // 1000,
                maximum=maximum_cny // 1000,
                unit="K_PER_MONTH",
                months=None,
            )
        return Salary(
            source_text=value,
            minimum=minimum_cny,
            maximum=maximum_cny,
            unit="CNY_PER_MONTH",
            months=None,
        )

    daily_match = DAILY_SALARY_PATTERN.fullmatch(value)
    if daily_match:
        minimum, maximum = daily_match.groups()
        minimum_value = int(minimum)
        maximum_value = int(maximum)
        _validate_salary_values(value, minimum_value, maximum_value, None)
        return Salary(
            source_text=value,
            minimum=minimum_value,
            maximum=maximum_value,
            unit="CNY_PER_DAY",
            months=None,
        )

    hourly_match = HOURLY_SALARY_PATTERN.fullmatch(value)
    if hourly_match:
        minimum, maximum = hourly_match.groups()
        minimum_value = int(minimum)
        maximum_value = int(maximum)
        _validate_salary_values(value, minimum_value, maximum_value, None)
        return Salary(
            source_text=value,
            minimum=minimum_value,
            maximum=maximum_value,
            unit="CNY_PER_HOUR",
            months=None,
        )

    raise SnapshotError(f"无法识别薪资格式: {value}")


def _validate_salary_values(
    source_text: str,
    minimum: int,
    maximum: int,
    months: int | None,
) -> None:
    if minimum <= 0 or maximum < minimum or (months is not None and months <= 0):
        raise SnapshotError(f"薪资数值不合法: {source_text}")


def parse_skills(value: str) -> list[str]:
    """拆分技能文本，并保持原顺序去重。"""
    skills: list[str] = []
    for part in value.split("|"):
        skill = part.strip()
        if skill and skill not in skills:
            skills.append(skill)
    return skills


def map_boss_job(raw_job: dict[str, str]) -> JobRecord:
    """将多条 Boss 直聘的岗位数据映射为每条岗位数据的标准化 JobRecord"""
    salary = parse_salary(raw_job["salary"])
    return JobRecord(
        source="boss_zhipin",
        external_id=raw_job["job_id"],
        title=raw_job["title"],
        company=raw_job["boss_name"],
        city=raw_job["location"].split("·", 1)[0],
        detail_url=raw_job["job_link"],
        salary_text=salary.source_text,
        salary_min=salary.minimum,
        salary_max=salary.maximum,
        salary_unit=salary.unit,
        salary_months=salary.months,
        skills=parse_skills(raw_job["skills"]),
    )


def map_boss_jobs(raw_jobs: list[dict[str, str]]) -> list[JobRecord]:
    """将多条 Boss 直聘的岗位数据映射为标准化 JobRecord 列表"""
    return [map_boss_job(raw_job) for raw_job in raw_jobs]


def load_boss_jobs(path: Path) -> list[dict[str, str]]:
    """从 JSON 文件中加载 Boss 直聘的岗位数据"""
    try:
        json_data = path.read_text(encoding="utf-8")  # 读取 JSON 文件内容
    except FileNotFoundError as exc:
        raise SnapshotError(f"没有找到快照文件: {path}") from exc

    try:
        snapshot_data = json.loads(json_data)  # 解析 JSON 数据
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"快照文件内容不是有效的 JSON 格式: {path}") from exc

    if "jobs" not in snapshot_data:
        raise SnapshotError(f"快照文件中缺少 'jobs' 键: {path}")

    if not isinstance(snapshot_data["jobs"], list):
        raise SnapshotError(f"快照文件中 'jobs' 键的值不是列表: {path}")

    required_keys = {
        "job_id",
        "title",
        "boss_name",
        "location",
        "job_link",
        "salary",
        "skills",
    }
    for num, job in enumerate(snapshot_data["jobs"], start=1):
        if not isinstance(job, dict):
            raise SnapshotError(f"快照文件中第 {num} 条岗位数据不是字典: {path}")

        missing_keys = required_keys - job.keys()

        if missing_keys:
            sorted_missing_keys = sorted(missing_keys)
            missing_keys_text = ", ".join(sorted_missing_keys)
            raise SnapshotError(f"快照文件中第 {num} 条岗位数据缺少键: {missing_keys_text}: {path}")

        for key in sorted(required_keys):
            value = job[key]

            if not isinstance(value, str):
                raise SnapshotError(
                    f"快照文件中第 {num} 条岗位数据的键 '{key}' 的值不是字符串: {path}"
                )

            if key != "skills" and value.strip() == "":
                raise SnapshotError(f"快照文件中第 {num} 条数据的 '{key}' 值为空: {path}")

    return snapshot_data["jobs"]
