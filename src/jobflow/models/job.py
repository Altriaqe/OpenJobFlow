from dataclasses import dataclass, field


@dataclass
class JobRecord:
    """岗位记录数据模型"""

    source: str
    external_id: str
    title: str
    company: str
    city: str
    detail_url: str
    salary_text: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_unit: str | None = None
    salary_months: int | None = None
    skills: list[str] = field(default_factory=list)
