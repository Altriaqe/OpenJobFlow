import re
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from jobflow.adapters.boss import load_boss_jobs, map_boss_jobs


ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PATH = ROOT / "examples" / "jobs.sample.json"
LICENSE_PATH = ROOT / "LICENSE"
ENGLISH_README = ROOT / "README.md"
CHINESE_README = ROOT / "README.zh-CN.md"
DOCS_INDEX = ROOT / "docs" / "README.md"
DEMO_IMAGE = ROOT / "docs" / "assets" / "jobflow-demo.png"
MARKDOWN_LINK = re.compile(r"!?\[[^]]*]\(([^)]+)\)")
WINDOWS_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9_])[A-Z]:\\(?![<>])")
UNIX_HOME_PATH = re.compile(r"/home/(?!<)[A-Za-z0-9._-]+(?:/|\\b)")
PRIVATE_NETWORK_ADDRESS = re.compile(
    r"(?<![\d<])(?:"
    r"10(?:\.\d{1,3}){3}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}"
    r")(?![\d>])"
)
AUTHENTICATED_URL = re.compile(r"https?://[^\s/:@]+:[^\s/@]+@[^\s]+")
PRIVATE_KEY_HEADER = re.compile("-----BE" + "GIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----")
KNOWN_SECRET = re.compile(
    r"(?:"
    r"sk-[A-Za-z0-9_-]{20,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|"
    r"AKIA[0-9A-Z]{16}|"
    r"\d{8,10}:[A-Za-z0-9_-]{30,}"
    r")"
)
PUBLIC_TEXT_SUFFIXES = {
    ".dockerignore",
    ".example",
    ".gitignore",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".yaml",
    ".yml",
}
PUBLIC_TEXT_FILENAMES = {"Dockerfile", "LICENSE"}


def _tracked_public_text_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    paths = (ROOT / item for item in result.stdout.split("\0") if item)
    return sorted(
        path
        for path in paths
        if path.name in PUBLIC_TEXT_FILENAMES or path.suffix.lower() in PUBLIC_TEXT_SUFFIXES
    )


def test_public_sample_is_valid_and_fully_synthetic() -> None:
    raw_jobs = load_boss_jobs(SAMPLE_PATH)
    records = map_boss_jobs(raw_jobs)

    assert len(raw_jobs) == 12
    assert len(records) == 12
    assert Counter(record.city for record in records) == {
        "上海": 4,
        "北京": 3,
        "杭州": 3,
        "深圳": 2,
    }
    assert {record.source for record in records} == {"boss_zhipin"}
    assert {job["salary"] for job in raw_jobs} >= {
        "15-25K",
        "20-30K·14薪",
        "5000-7000元/月",
        "3500-5500元/月",
        "200-300元/天",
        "50-60元/时",
        "面议",
    }
    assert all(job["job_id"].startswith("demo-") for job in raw_jobs)
    assert all("示例" in job["boss_name"] for job in raw_jobs)
    assert all(urlparse(job["job_link"]).hostname == "example.com" for job in raw_jobs)


def test_license_is_standard_mit_for_jobflow() -> None:
    text = LICENSE_PATH.read_text(encoding="utf-8")

    assert text.startswith("MIT License\n")
    assert "Copyright (c) 2026 Altriaqe" in text
    assert "Permission is hereby granted, free of charge" in text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in text
    assert "<year>" not in text
    assert "<copyright holders>" not in text


def test_public_demo_image_is_a_real_png() -> None:
    image = DEMO_IMAGE.read_bytes()

    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(image) > 10_000


def test_english_readme_has_public_onboarding_contract() -> None:
    text = ENGLISH_README.read_text(encoding="utf-8")

    required = (
        "# JobFlow",
        "[简体中文](README.zh-CN.md)",
        "## Why JobFlow",
        "## Key Features",
        "## Architecture",
        "## Quick Start",
        "## API and Demo Output",
        "## Technology Stack",
        "## Project Structure",
        "## Optional AI Summary",
        "## Optional Telegram Delivery",
        "## Ubuntu Deployment",
        "## Configuration and DIY",
        "## Development and Testing",
        "## Data, Security, and Compliance",
        "## Roadmap",
        "## Contributing",
        "## License",
        "## Documentation",
        "examples/jobs.sample.json",
        "docs/assets/jobflow-demo.png",
        "docker compose run --rm etl /data/raw/inbox/jobs.json",
        "http://127.0.0.1:8000/ready",
    )
    assert all(item in text for item in required)
    assert "production-ready" not in text.lower()


def test_chinese_readme_has_matching_public_onboarding_contract() -> None:
    text = CHINESE_README.read_text(encoding="utf-8")

    required = (
        "# JobFlow",
        "[English](README.md)",
        "## 为什么使用 JobFlow",
        "## 核心能力",
        "## 架构与数据流",
        "## 10 分钟 Docker 复现",
        "## API 与演示效果",
        "## 技术栈",
        "## 项目结构",
        "## 可选 AI 总结",
        "## 可选 Telegram 推送",
        "## Ubuntu 部署",
        "## 配置与 DIY",
        "## 本地开发与测试",
        "## 数据、安全与合规",
        "## 路线图",
        "## 参与贡献",
        "## 许可证",
        "## 详细文档",
        "examples/jobs.sample.json",
        "docs/assets/jobflow-demo.png",
        "docker compose run --rm etl /data/raw/inbox/jobs.json",
        "http://127.0.0.1:8000/ready",
    )
    assert all(item in text for item in required)


def test_bilingual_readmes_keep_critical_commands_and_links_in_sync() -> None:
    english = ENGLISH_README.read_text(encoding="utf-8")
    chinese = CHINESE_README.read_text(encoding="utf-8")
    shared = (
        "examples/jobs.sample.json",
        "docs/assets/jobflow-demo.png",
        "cp .env.example .env",
        "Copy-Item .env.example .env",
        "docker compose build api",
        "docker compose up -d postgres",
        "docker compose run --rm migrate",
        "docker compose run --rm etl /data/raw/inbox/jobs.json",
        "docker compose up -d api",
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:8000/ready",
        "http://127.0.0.1:8000/docs",
        "docs/ubuntu-deployment.md",
        "LICENSE",
    )
    for item in shared:
        assert item in english
        assert item in chinese


def test_bilingual_readme_local_links_resolve() -> None:
    for readme in (ENGLISH_README, CHINESE_README):
        text = readme.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(text):
            if target.startswith(("http://", "https://", "#")):
                continue
            relative_target = target.split("#", 1)[0]
            assert (readme.parent / relative_target).exists(), (
                f"broken local link in {readme.name}: {target}"
            )


def test_docs_index_points_to_bilingual_public_entrypoints() -> None:
    text = DOCS_INDEX.read_text(encoding="utf-8")

    assert "../README.md" in text
    assert "../README.zh-CN.md" in text
    assert "assets/jobflow-demo.png" in text


def test_tracked_public_text_does_not_expose_personal_environment() -> None:
    violations: list[str] = []
    patterns = {
        "Windows absolute path": WINDOWS_ABSOLUTE_PATH,
        "literal Unix home": UNIX_HOME_PATH,
        "private network address": PRIVATE_NETWORK_ADDRESS,
        "authenticated URL": AUTHENTICATED_URL,
        "private key": PRIVATE_KEY_HEADER,
        "known secret format": KNOWN_SECRET,
    }

    for path in _tracked_public_text_files():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for label, pattern in patterns.items():
                if pattern.search(line):
                    relative_path = path.relative_to(ROOT).as_posix()
                    violations.append(f"{relative_path}:{line_number}: {label}")

    assert not violations, "personal environment references found:\n" + "\n".join(violations)
