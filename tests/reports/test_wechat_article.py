from datetime import date
import json
import os
from pathlib import Path
import stat

import pytest

from jobflow.models.snapshot import (
    DailyComparison,
    KeywordTrend,
    MetricChange,
    NewJobPosting,
)
from jobflow.reports.wechat_article import (
    KeywordNewJobs,
    WechatArticleData,
    _requirement_labels,
    build_article_data,
    write_wechat_article,
)


PNG = b"\x89PNG\r\n\x1a\narticle"
COVER = b"\x89PNG\r\n\x1a\ncover"


def posting(
    external_id: str,
    *,
    title: str = "AI Agent 工程师",
    salary_text: str | None = None,
    skills: tuple[str, ...] = ("Python", "LLM"),
    detail_url: str | None = "https://example.test/jobs/1",
) -> NewJobPosting:
    return NewJobPosting(
        source="boss_zhipin",
        external_id=external_id,
        keyword="AI Agent",
        title=title,
        company="<示例>公司",
        city="上海",
        salary_text=salary_text,
        salary_min=None,
        salary_max=None,
        salary_unit=None,
        salary_months=None,
        skills=skills,
        detail_url=detail_url,
    )


@pytest.mark.parametrize(
    ("skills", "expected"),
    [
        (("Java", "统招本科", "Spring"), ("本科", "Java、Spring")),
        (("Java", "Spring"), (None, "Java、Spring")),
        (("统招本科",), ("本科", "暂无明确技能标签")),
        (("本科", "硕士", "Python"), ("本科", "Python")),
        (("  ", "Python"), (None, "Python")),
    ],
)
def test_requirement_labels_extract_education_and_filter_skills(
    skills: tuple[str, ...],
    expected: tuple[str | None, str],
) -> None:
    assert _requirement_labels(posting("requirements", skills=skills)) == expected


def sample_data() -> WechatArticleData:
    return WechatArticleData(
        report_date=date(2026, 8, 26),
        city_count=4,
        cities=("上海", "北京", "杭州", "深圳"),
        pages_per_city=3,
        keyword_rows=(("AI Agent", 18, 3), ("Python开发", 21, None)),
        city_advantages=(("上海", "AI Agent", 5), ("北京", "Python开发", 7)),
        weekly_summary=None,
        new_job_groups=(
            KeywordNewJobs(
                "AI Agent",
                (
                    posting("job-1", salary_text="250-350元/天"),
                    posting(
                        "job-2",
                        skills=(),
                        detail_url="https://example.test/jobs/2",
                    ),
                    posting(
                        "job-3",
                        title="Python & Agent",
                        salary_text="15-30K·16薪",
                        detail_url="https://example.test/jobs/3",
                    ),
                ),
            ),
            KeywordNewJobs("Python开发", None),
        ),
    )


def test_article_package_contains_machine_and_official_account_markdown(tmp_path):
    manifest = write_wechat_article(sample_data(), PNG, COVER, tmp_path / "wechat")
    import_filename = "2026-08-26 每日新增岗位公告.md"

    assert manifest.files == (
        "article.md",
        import_filename,
        "article.html",
        "cover.png",
        "trend.png",
        "manifest.json",
    )
    assert manifest.new_job_count == 3
    assert (tmp_path / "wechat" / "trend.png").read_bytes() == PNG
    assert (tmp_path / "wechat" / "cover.png").read_bytes() == COVER
    machine_markdown = (tmp_path / "wechat" / "article.md").read_text(encoding="utf-8")
    import_markdown = (tmp_path / "wechat" / import_filename).read_text(encoding="utf-8")
    assert machine_markdown.startswith("# 2026-08-26 每日新增岗位公告\n")
    assert import_markdown.startswith("> 今日新增岗位：3\n")
    assert "# 2026-08-26 每日新增岗位公告" not in import_markdown
    assert machine_markdown.split("\n", 2)[2] == import_markdown
    payload = json.loads((tmp_path / "wechat" / "manifest.json").read_text(encoding="utf-8"))
    assert payload["report_date"] == "2026-08-26"
    assert payload["keyword_counts"] == [["AI Agent", 3], ["Python开发", None]]


def test_html_has_no_script_remote_resource_or_sensitive_fields(tmp_path):
    write_wechat_article(sample_data(), PNG, COVER, tmp_path / "wechat")
    html = (tmp_path / "wechat" / "article.html").read_text(encoding="utf-8")

    assert "<script" not in html.lower()
    assert "http://" not in html.lower()
    assert 'src="http' not in html.lower()
    assert "openid" not in html.lower()
    assert "appsecret" not in html.lower()
    assert html.count('class="job-card"') == 3
    assert "&lt;示例&gt;公司" in html
    assert "岗位原始地址（复制后打开）：<br>https://example.test/jobs/1" in html
    assert html.count("岗位原始地址（复制后打开）：<br>https://example.test/jobs/") == 3
    assert 'href="https://example.test/jobs/' not in html
    assert "暂无明确技能标签" in html
    assert "薪资面议" in html
    assert 'src="trend.png"' in html
    assert "学历要求：" not in html
    assert (
        "<p>岗位信息来源于公开招聘页面，仅供学习研究。"
        "请以招聘平台原始页面及招聘方实际信息为准。</p>"
    ) in html
    assert "固定页数招聘岗位样本" not in html
    assert "今日新增岗位：3" in html
    assert "搜索关键词：AI Agent、Python开发" in html
    assert "覆盖城市：上海、北京、杭州、深圳" in html
    assert "今日新增岗位样本" not in html
    assert "采集口径" not in html


def test_markdown_uses_official_account_compatible_job_blocks(tmp_path):
    write_wechat_article(sample_data(), PNG, COVER, tmp_path / "wechat")
    markdown = (tmp_path / "wechat" / "article.md").read_text(encoding="utf-8")

    assert "#### AI Agent 工程师" not in markdown
    assert "**AI Agent 工程师｜250-350元/天**" in markdown
    assert "**AI Agent 工程师｜薪资面议**" in markdown
    assert "**Python & Agent｜15-30K·16薪**" in markdown
    assert "**<示例>公司**" in markdown
    assert markdown.count("\n---\n") == 2
    assert "岗位原始地址（复制后打开）：\nhttps://example.test/jobs/1" in markdown
    assert markdown.count("岗位原始地址（复制后打开）：\nhttps://example.test/jobs/") == 3
    assert "[查看岗位详情 →](" not in markdown
    assert markdown.endswith(
        "岗位信息来源于公开招聘页面，仅供学习研究。请以招聘平台原始页面及招聘方实际信息为准。\n"
    )
    assert "固定页数招聘岗位样本" not in markdown
    assert "> 今日新增岗位：3" in markdown
    assert "> 搜索关键词：AI Agent、Python开发" in markdown
    assert "> 覆盖城市：上海、北京、杭州、深圳" in markdown
    assert "今日新增岗位样本" not in markdown
    assert "采集口径" not in markdown


def test_markdown_and_html_render_education_without_repeating_skill_tag(tmp_path):
    data = sample_data()
    groups = (
        KeywordNewJobs(
            "AI Agent",
            (posting("education", skills=("Java", "统招本科", "Spring")),),
        ),
        KeywordNewJobs("Python开发", None),
    )
    data = WechatArticleData(
        data.report_date,
        data.city_count,
        data.cities,
        data.pages_per_city,
        data.keyword_rows,
        data.city_advantages,
        data.weekly_summary,
        groups,
    )

    write_wechat_article(data, PNG, COVER, tmp_path / "wechat")
    markdown = (tmp_path / "wechat" / "article.md").read_text(encoding="utf-8")
    document = (tmp_path / "wechat" / "article.html").read_text(encoding="utf-8")

    assert "学历要求：本科" in markdown
    assert "技能要求：Java、Spring" in markdown
    assert "学历要求：本科" in document
    assert "技能要求：Java、Spring" in document
    assert "技能要求：Java、统招本科、Spring" not in markdown
    assert "技能要求：Java、统招本科、Spring" not in document


def test_markdown_and_html_hide_education_when_source_does_not_provide_it(tmp_path):
    write_wechat_article(sample_data(), PNG, COVER, tmp_path / "wechat")
    markdown = (tmp_path / "wechat" / "article.md").read_text(encoding="utf-8")
    document = (tmp_path / "wechat" / "article.html").read_text(encoding="utf-8")

    assert "学历要求：" not in markdown
    assert "学历要求：" not in document


def test_markdown_and_html_hide_job_url_when_source_does_not_provide_it(tmp_path):
    data = sample_data()
    groups = (
        KeywordNewJobs("AI Agent", (posting("without-url", detail_url=None),)),
        KeywordNewJobs("Python开发", None),
    )
    data = WechatArticleData(
        data.report_date,
        data.city_count,
        data.cities,
        data.pages_per_city,
        data.keyword_rows,
        data.city_advantages,
        data.weekly_summary,
        groups,
    )

    write_wechat_article(data, PNG, COVER, tmp_path / "wechat")
    markdown = (tmp_path / "wechat" / "article.md").read_text(encoding="utf-8")
    document = (tmp_path / "wechat" / "article.html").read_text(encoding="utf-8")

    assert "岗位原始地址（复制后打开）：" not in markdown
    assert "岗位原始地址（复制后打开）：" not in document


def test_invalid_image_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="PNG"):
        write_wechat_article(sample_data(), b"not-an-image", COVER, tmp_path / "wechat")


def test_article_cities_must_match_city_count(tmp_path):
    data = sample_data()
    invalid = WechatArticleData(
        data.report_date,
        data.city_count,
        ("上海", "北京"),
        data.pages_per_city,
        data.keyword_rows,
        data.city_advantages,
        data.weekly_summary,
        data.new_job_groups,
    )

    with pytest.raises(ValueError, match="cities must match city_count"):
        write_wechat_article(invalid, PNG, COVER, tmp_path / "wechat")


def test_invalid_or_unsafe_job_fields_are_rejected(tmp_path):
    data = sample_data()
    unsafe = KeywordNewJobs(
        "AI Agent",
        (posting("bad", detail_url="javascript:alert(1)"),),
    )
    data = WechatArticleData(
        data.report_date,
        data.city_count,
        data.cities,
        data.pages_per_city,
        data.keyword_rows,
        data.city_advantages,
        data.weekly_summary,
        (unsafe, KeywordNewJobs("Python开发", None)),
    )

    with pytest.raises(ValueError, match="detail URL"):
        write_wechat_article(data, PNG, COVER, tmp_path / "wechat")


@pytest.mark.parametrize("field", ["title", "company", "city"])
def test_required_job_fields_must_not_be_blank(tmp_path, field):
    item = posting("blank")
    values = item.__dict__ | {field: "  "}
    group = KeywordNewJobs("AI Agent", (NewJobPosting(**values),))
    data = sample_data()
    data = WechatArticleData(
        data.report_date,
        data.city_count,
        data.cities,
        data.pages_per_city,
        data.keyword_rows,
        data.city_advantages,
        data.weekly_summary,
        (group, KeywordNewJobs("Python开发", None)),
    )

    with pytest.raises(ValueError, match="title, company and city"):
        write_wechat_article(data, PNG, COVER, tmp_path / "wechat")


def test_complete_baseline_with_zero_new_jobs_renders_empty_notice(tmp_path):
    data = sample_data()
    data = WechatArticleData(
        data.report_date,
        data.city_count,
        data.cities,
        data.pages_per_city,
        data.keyword_rows,
        data.city_advantages,
        data.weekly_summary,
        (KeywordNewJobs("AI Agent", ()), KeywordNewJobs("Python开发", ())),
    )

    write_wechat_article(data, PNG, COVER, tmp_path / "wechat")
    html = (tmp_path / "wechat" / "article.html").read_text(encoding="utf-8")

    assert "今日暂无新增岗位" in html
    assert 'class="job-card"' not in html


def test_build_article_data_reuses_keyword_trend_metrics():
    daily = DailyComparison(
        has_baseline=True,
        total=MetricChange(10, 8, 2, None),
        city_metrics=(),
        new_count=2,
        continued_count=None,
        missing_count=None,
        skills=(),
        salary_midpoint_median=MetricChange(None, None, None, None),
    )
    trends = (KeywordTrend("AI Agent", daily, None),)

    data = build_article_data(
        report_date=date(2026, 8, 26),
        trends=trends,
        city_count=4,
        cities=("上海", "北京", "杭州", "深圳"),
        pages_per_city=3,
    )

    assert data.keyword_rows == (("AI Agent", 10, 2),)
    assert data.cities == ("上海", "北京", "杭州", "深圳")


def test_article_package_can_be_replaced_as_a_complete_directory(tmp_path):
    output = tmp_path / "wechat"
    write_wechat_article(sample_data(), PNG, COVER, output)
    (output / "stale.txt").write_text("old", encoding="utf-8")

    write_wechat_article(sample_data(), PNG, COVER, output)

    assert not (output / "stale.txt").exists()
    assert {path.name for path in output.iterdir()} == {
        "article.md",
        "2026-08-26 每日新增岗位公告.md",
        "article.html",
        "cover.png",
        "trend.png",
        "manifest.json",
    }


def test_article_package_sets_explicit_permissions(tmp_path, monkeypatch):
    """跨平台确认实现主动设置文件与目录权限，而不是依赖 umask。"""
    chmod_calls: list[tuple[str, int]] = []
    original_chmod = Path.chmod

    def record_chmod(path: Path, mode: int) -> None:
        chmod_calls.append((path.name, mode))
        original_chmod(path, mode)

    monkeypatch.setattr(Path, "chmod", record_chmod)

    output = tmp_path / "wechat"
    manifest = write_wechat_article(sample_data(), PNG, COVER, output)

    file_modes = {name: mode for name, mode in chmod_calls if name in manifest.files}
    assert file_modes == {name: 0o644 for name in manifest.files}
    assert (
        sum(name.startswith("wechat-article-") and mode == 0o755 for name, mode in chmod_calls) == 1
    )


@pytest.mark.skipif(os.name == "nt", reason="需要 POSIX 权限位语义")
def test_article_package_permissions_survive_atomic_replacement(tmp_path):
    """Linux 首次生成和覆盖生成后都必须保持宿主机可读权限。"""
    output = tmp_path / "wechat"

    for _ in range(2):
        manifest = write_wechat_article(sample_data(), PNG, COVER, output)

        assert stat.S_IMODE(output.stat().st_mode) == 0o755
        for filename in manifest.files:
            assert stat.S_IMODE((output / filename).stat().st_mode) == 0o644
