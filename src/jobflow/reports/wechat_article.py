"""微信公众号文章排版包生成器：只消费聚合数据和已生成的 PNG。"""

from dataclasses import dataclass
from datetime import date
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlparse

from jobflow.models.snapshot import KeywordTrend, NewJobPosting


@dataclass(frozen=True)
class KeywordNewJobs:
    """一个关键词的新增岗位；None 表示缺少可比较的前日基线。"""

    keyword: str
    postings: tuple[NewJobPosting, ...] | None

    @property
    def has_baseline(self) -> bool:
        return self.postings is not None


@dataclass(frozen=True)
class WechatArticleData:
    """文章生成所需的脱敏聚合数据，不包含岗位明细或个人配置。"""

    report_date: date
    city_count: int
    pages_per_city: int
    keyword_rows: tuple[tuple[str, int, int | None], ...]
    city_advantages: tuple[tuple[str, str, int], ...]
    weekly_summary: str | None = None
    new_job_groups: tuple[KeywordNewJobs, ...] = ()


@dataclass(frozen=True)
class ArticleManifest:
    """排版包清单，便于人工发布前检查文件是否完整。"""

    report_date: str
    files: tuple[str, ...]
    new_job_count: int
    keyword_counts: tuple[tuple[str, int | None], ...]
    cover_sha256: str
    trend_sha256: str


def build_article_data(
    *,
    report_date: date,
    trends: tuple[KeywordTrend, ...],
    city_count: int,
    pages_per_city: int,
    new_job_groups: tuple[KeywordNewJobs, ...] = (),
) -> WechatArticleData:
    """把统一多关键词趋势转换为文章输入，避免微信渠道重复计算指标。"""
    if not trends:
        raise ValueError("trends must not be empty")
    keyword_rows = tuple(
        (
            trend.keyword,
            int(trend.daily.total.current or 0),
            trend.daily.new_count,
        )
        for trend in trends
    )
    city_advantages: list[tuple[str, str, int]] = []
    if all(trend.new_by_city is not None for trend in trends):
        cities = tuple(metric.name for metric in trends[0].new_by_city or ())
        for city in cities:
            values = [
                (
                    trend.keyword,
                    next(metric.count for metric in trend.new_by_city or () if metric.name == city),
                )
                for trend in trends
            ]
            best_keyword, best_count = min(values, key=lambda item: (-item[1], item[0]))
            city_advantages.append((city, best_keyword, best_count))
    weekly_summary = None
    if report_date.weekday() == 6 and all(trend.weekly is not None for trend in trends):
        weekly_summary = "；".join(
            f"{trend.keyword}：本周 {trend.weekly.total.current}，较上周 {trend.weekly.total.delta:+}"
            for trend in trends
            if trend.weekly is not None
        )
    return WechatArticleData(
        report_date=report_date,
        city_count=city_count,
        pages_per_city=pages_per_city,
        keyword_rows=keyword_rows,
        city_advantages=tuple(city_advantages),
        weekly_summary=weekly_summary,
        new_job_groups=new_job_groups,
    )


def _validate(data: WechatArticleData, trend_png: bytes, cover_png: bytes) -> None:
    if data.city_count <= 0 or data.pages_per_city <= 0:
        raise ValueError("article scope must be positive")
    if not data.keyword_rows:
        raise ValueError("article requires keyword rows")
    if not trend_png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("trend image must be a PNG")
    if not cover_png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("cover image must be a PNG")
    keywords = [row[0].strip() for row in data.keyword_rows]
    if any(not keyword for keyword in keywords) or len(set(keywords)) != len(keywords):
        raise ValueError("keywords must be non-empty and unique")
    for keyword, total, new_count in data.keyword_rows:
        if total < 0 or (new_count is not None and new_count < 0):
            raise ValueError(f"invalid metric for keyword: {keyword}")
    group_keywords = [group.keyword.strip() for group in data.new_job_groups]
    if any(not keyword for keyword in group_keywords) or len(set(group_keywords)) != len(
        group_keywords
    ):
        raise ValueError("new-job keywords must be non-empty and unique")
    if group_keywords and group_keywords != keywords:
        raise ValueError("new-job groups must match keyword report order")
    for group in data.new_job_groups:
        if group.postings is None:
            continue
        identities: set[tuple[str, str]] = set()
        for posting in group.postings:
            if posting.keyword != group.keyword:
                raise ValueError("posting keyword does not match its group")
            if posting.identity in identities:
                raise ValueError("job identities must be unique within a keyword")
            identities.add(posting.identity)
            if not posting.title.strip() or not posting.company.strip() or not posting.city.strip():
                raise ValueError("job title, company and city must not be empty")
            if posting.detail_url:
                parsed = urlparse(posting.detail_url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ValueError("detail URL must use http or https")


def _sorted_postings(postings: tuple[NewJobPosting, ...]) -> tuple[NewJobPosting, ...]:
    return tuple(
        sorted(
            postings,
            key=lambda item: (item.city, item.title, item.external_id, item.source),
        )
    )


def _salary_label(posting: NewJobPosting) -> str:
    return (
        posting.salary_text.strip()
        if posting.salary_text and posting.salary_text.strip()
        else "薪资面议"
    )


_EDUCATION_LABELS = ("学历不限", "中专", "高中", "大专", "本科", "硕士", "博士")


def _education_label(value: str) -> str | None:
    """把包含明确学历词的岗位标签规范化为学历显示值。"""
    for label in _EDUCATION_LABELS:
        if label in value:
            return label
    return None


def _requirement_labels(posting: NewJobPosting) -> tuple[str, str]:
    """返回学历要求与移除学历标签后的技能要求。"""
    education: str | None = None
    skills: list[str] = []
    for raw_value in posting.skills:
        value = raw_value.strip()
        if not value:
            continue
        detected = _education_label(value)
        if detected is not None:
            if education is None:
                education = detected
            continue
        skills.append(value)
    return education or "未注明", "、".join(skills) or "暂无明确技能标签"


def _new_job_count(data: WechatArticleData) -> int:
    return sum(len(group.postings) for group in data.new_job_groups if group.postings is not None)


def _build_markdown(data: WechatArticleData) -> str:
    lines = [
        f"# {data.report_date.isoformat()} 每日新增岗位公告",
        "",
        f"> 今日新增岗位样本：{_new_job_count(data)}",
        f"> 搜索关键词：{len(data.keyword_rows)}",
        f"> 覆盖城市：{data.city_count}",
        f"> 采集口径：每关键词 × 每城市固定 {data.pages_per_city} 页",
        "",
        "## 关键词趋势",
        "",
        "| 关键词 | 当前样本 | 较前日新增 |",
        "| --- | ---: | ---: |",
    ]
    for keyword, total, new_count in data.keyword_rows:
        change = "基线建立中" if new_count is None else str(new_count)
        lines.append(f"| {keyword} | {total} | {change} |")
    lines.extend(["", "## 城市优势组合", ""])
    for city, keyword, count in data.city_advantages:
        lines.append(f"- {city}：{keyword} 新增样本最多（{count} 条）")
    lines.extend(["", "## 趋势图", "", "![多关键词城市趋势](trend.png)"])
    if data.weekly_summary:
        lines.extend(["", "## 周对比", "", data.weekly_summary])
    lines.extend(["", "## 今日新增岗位", ""])
    if data.new_job_groups and all(
        group.postings is not None and not group.postings for group in data.new_job_groups
    ):
        lines.extend(["今日暂无新增岗位。", ""])
    for group in data.new_job_groups:
        if group.postings is None:
            lines.extend([f"### {group.keyword} · 基线建立中", ""])
            continue
        lines.extend([f"### {group.keyword} · 新增 {len(group.postings)} 个", ""])
        for posting in _sorted_postings(group.postings):
            education_label, skills_label = _requirement_labels(posting)
            lines.extend(
                [
                    f"#### {posting.title}　{_salary_label(posting)}",
                    "",
                    posting.company,
                    "",
                    f"工作地点：{posting.city}",
                    "",
                    f"学历要求：{education_label}",
                    "",
                    f"技能要求：{skills_label}",
                ]
            )
            if posting.detail_url:
                lines.extend(["", f"[查看岗位详情 →]({posting.detail_url})"])
            lines.append("")
    lines.extend(["", "数据来源：固定页数招聘岗位样本，仅供学习研究。", ""])
    return "\n".join(lines)


def _build_html(data: WechatArticleData) -> str:
    """生成无脚本、无远程资源的静态 HTML，便于复制到公众号编辑器。"""
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(keyword)}</td><td>{total}</td>"
        f"<td>{'基线建立中' if new_count is None else new_count}</td>"
        "</tr>"
        for keyword, total, new_count in data.keyword_rows
    )
    title = html.escape(f"{data.report_date.isoformat()} 每日新增岗位公告")
    groups: list[str] = []
    if data.new_job_groups and all(
        group.postings is not None and not group.postings for group in data.new_job_groups
    ):
        groups.append('<p class="empty">今日暂无新增岗位。</p>')
    for group in data.new_job_groups:
        keyword = html.escape(group.keyword, quote=True)
        if group.postings is None:
            groups.append(f"<section><h3>{keyword} · 基线建立中</h3></section>")
            continue
        cards = []
        for posting in _sorted_postings(group.postings):
            link = ""
            if posting.detail_url:
                url = html.escape(posting.detail_url, quote=True)
                link = (
                    f'<a href="{url}" target="_blank" rel="noopener noreferrer">查看岗位详情 →</a>'
                )
            education_label, skills_label = _requirement_labels(posting)
            cards.append(
                '<article class="job-card">'
                '<div class="job-heading">'
                f"<h4>{html.escape(posting.title)}</h4>"
                f'<span class="salary">{html.escape(_salary_label(posting))}</span>'
                "</div>"
                f'<p class="company">{html.escape(posting.company)}</p>'
                f"<p>工作地点：{html.escape(posting.city)}</p>"
                f"<p>学历要求：{html.escape(education_label)}</p>"
                f"<p>技能要求：{html.escape(skills_label)}</p>"
                f"{link}</article>"
            )
        groups.append(
            f"<section><h3>{keyword} · 新增 {len(group.postings)} 个</h3>"
            + "".join(cards)
            + "</section>"
        )
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        f"<title>{title}</title><style>body{{max-width:760px;margin:auto;padding:24px;"
        "font-family:Arial,'Microsoft YaHei',sans-serif;color:#182230;line-height:1.7}}"
        ".summary{background:#eef4ff;padding:16px;border-radius:12px}.job-card{border:1px solid "
        "#dbe4f0;border-radius:14px;padding:18px;margin:14px 0}.job-heading{display:flex;gap:16px;"
        "justify-content:space-between;align-items:flex-start}.job-heading h4{margin:0}.salary{color:#e05a2a;"
        "font-weight:700;white-space:nowrap}.company{font-weight:600}a{color:#1738c8;text-decoration:none}"
        ".empty{padding:24px;text-align:center;background:#f5f7fa;border-radius:12px}</style></head><body>"
        f"<h1>{title}</h1>"
        f'<div class="summary"><p>今日新增岗位样本：{_new_job_count(data)}<br>'
        f"搜索关键词：{len(data.keyword_rows)}<br>覆盖城市：{data.city_count}<br>"
        f"采集口径：每关键词 × 每城市固定 {data.pages_per_city} 页</p></div>"
        "<h2>关键词趋势</h2><table><thead><tr><th>关键词</th>"
        "<th>当前样本</th><th>较前日新增</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        "<h2>城市优势组合</h2><ul>"
        + "".join(
            f"<li>{html.escape(city)}：{html.escape(keyword)} 新增样本最多（{count} 条）</li>"
            for city, keyword, count in data.city_advantages
        )
        + "</ul>"
        + '<h2>趋势图</h2><img src="trend.png" alt="多关键词城市趋势">'
        + (
            f"<h2>周对比</h2><p>{html.escape(data.weekly_summary)}</p>"
            if data.weekly_summary
            else ""
        )
        + "<h2>今日新增岗位</h2>"
        + "".join(groups)
        + "<p>数据来源：固定页数招聘岗位样本，仅供学习研究。</p></body></html>"
    )


def write_wechat_article(
    data: WechatArticleData,
    trend_png: bytes,
    cover_png: bytes,
    output_dir: Path,
) -> ArticleManifest:
    """原子写出五件套文章包，并返回不含敏感信息的清单。"""
    _validate(data, trend_png, cover_png)
    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    markdown = _build_markdown(data)
    document = _build_html(data)
    trend_digest = hashlib.sha256(trend_png).hexdigest()
    cover_digest = hashlib.sha256(cover_png).hexdigest()
    keyword_counts = tuple(
        (group.keyword, None if group.postings is None else len(group.postings))
        for group in data.new_job_groups
    )
    manifest = ArticleManifest(
        report_date=data.report_date.isoformat(),
        files=("article.md", "article.html", "cover.png", "trend.png", "manifest.json"),
        new_job_count=_new_job_count(data),
        keyword_counts=keyword_counts,
        cover_sha256=cover_digest,
        trend_sha256=trend_digest,
    )
    temp_dir = Path(tempfile.mkdtemp(prefix="wechat-article-", dir=output_dir.parent))
    backup_dir: Path | None = None
    try:
        (temp_dir / "article.md").write_text(markdown, encoding="utf-8")
        (temp_dir / "article.html").write_text(document, encoding="utf-8")
        (temp_dir / "cover.png").write_bytes(cover_png)
        (temp_dir / "trend.png").write_bytes(trend_png)
        (temp_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "report_date": manifest.report_date,
                    "files": manifest.files,
                    "new_job_count": manifest.new_job_count,
                    "keyword_counts": manifest.keyword_counts,
                    "cover_sha256": cover_digest,
                    "trend_sha256": trend_digest,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        # mkdtemp 默认创建 0700 目录；显式开放只读权限，方便宿主机维护者
        # 直接检查和复制文章包，同时保留只有容器用户可以修改的边界。
        for filename in manifest.files:
            (temp_dir / filename).chmod(0o644)
        temp_dir.chmod(0o755)
        if output_dir.exists():
            backup_dir = Path(tempfile.mkdtemp(prefix="wechat-previous-", dir=output_dir.parent))
            backup_dir.rmdir()
            os.replace(output_dir, backup_dir)
        try:
            os.replace(temp_dir, output_dir)
        except Exception:
            if backup_dir is not None and backup_dir.exists():
                os.replace(backup_dir, output_dir)
            raise
        if backup_dir is not None:
            shutil.rmtree(backup_dir)
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    return manifest
