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

from jobflow.models.snapshot import KeywordTrend


@dataclass(frozen=True)
class WechatArticleData:
    """文章生成所需的脱敏聚合数据，不包含岗位明细或个人配置。"""

    report_date: date
    city_count: int
    pages_per_city: int
    keyword_rows: tuple[tuple[str, int, int | None], ...]
    city_advantages: tuple[tuple[str, str, int], ...]
    weekly_summary: str | None = None


@dataclass(frozen=True)
class ArticleManifest:
    """排版包清单，便于人工发布前检查文件是否完整。"""

    report_date: str
    files: tuple[str, ...]
    trend_sha256: str


def build_article_data(
    *,
    report_date: date,
    trends: tuple[KeywordTrend, ...],
    city_count: int,
    pages_per_city: int,
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
    )


def _validate(data: WechatArticleData, trend_png: bytes) -> None:
    if data.city_count <= 0 or data.pages_per_city <= 0:
        raise ValueError("article scope must be positive")
    if not data.keyword_rows:
        raise ValueError("article requires keyword rows")
    if not trend_png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("trend image must be a PNG")
    keywords = [row[0].strip() for row in data.keyword_rows]
    if any(not keyword for keyword in keywords) or len(set(keywords)) != len(keywords):
        raise ValueError("keywords must be non-empty and unique")
    for keyword, total, new_count in data.keyword_rows:
        if total < 0 or (new_count is not None and new_count < 0):
            raise ValueError(f"invalid metric for keyword: {keyword}")


def _build_markdown(data: WechatArticleData) -> str:
    lines = [
        f"# JobFlow 招聘数据日报｜{data.report_date.isoformat()}",
        "",
        f"> 固定范围样本：{data.city_count} 个城市，每城 {data.pages_per_city} 页；仅供学习研究，不代表全市场总量。",
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
    lines.extend(["", "数据来源：固定页数招聘岗位样本，仅供学习研究。", ""])
    return "\n".join(lines)


def _build_html(markdown: str, data: WechatArticleData) -> str:
    """生成无脚本、无远程资源的静态 HTML，便于复制到公众号编辑器。"""
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(keyword)}</td><td>{total}</td>"
        f"<td>{'基线建立中' if new_count is None else new_count}</td>"
        "</tr>"
        for keyword, total, new_count in data.keyword_rows
    )
    title = html.escape(f"JobFlow 招聘数据日报｜{data.report_date.isoformat()}")
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        f"<title>{title}</title></head><body>"
        f"<h1>{title}</h1>"
        f"<p>固定范围样本：{data.city_count} 个城市，每城 {data.pages_per_city} 页；"
        "仅供学习研究，不代表全市场总量。</p>"
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
        + "<p>数据来源：固定页数招聘岗位样本，仅供学习研究。</p></body></html>"
    )


def write_wechat_article(
    data: WechatArticleData,
    trend_png: bytes,
    output_dir: Path,
) -> ArticleManifest:
    """原子写出四件套文章包，并返回不含敏感信息的清单。"""
    _validate(data, trend_png)
    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    markdown = _build_markdown(data)
    document = _build_html(markdown, data)
    digest = hashlib.sha256(trend_png).hexdigest()
    manifest = ArticleManifest(
        report_date=data.report_date.isoformat(),
        files=("article.md", "article.html", "trend.png", "manifest.json"),
        trend_sha256=digest,
    )
    temp_dir = Path(tempfile.mkdtemp(prefix="wechat-article-", dir=output_dir.parent))
    backup_dir: Path | None = None
    try:
        (temp_dir / "article.md").write_text(markdown, encoding="utf-8")
        (temp_dir / "article.html").write_text(document, encoding="utf-8")
        (temp_dir / "trend.png").write_bytes(trend_png)
        (temp_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "report_date": manifest.report_date,
                    "files": manifest.files,
                    "trend_sha256": digest,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
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
