# OpenJobFlow V1.3.3 微信每日新增岗位公告 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于同关键词前日快照差集，自动生成包含当天全部新增岗位的微信公众号五件套文章包，供人工审核后以“今日新增岗位”标准图文卡片发布，同时保持 Telegram 行为不变。

**Architecture:** 数据库层按 `source + external_id` 查询当天新增岗位并联查 `core.jobs.detail_url`；报告层把新增岗位分组加入 `WechatArticleData`，使用确定性 Matplotlib 封面和现有原子目录替换生成五件套；FastAPI 提供受 Bearer Token 保护的生成与状态接口，正式每日 Shell 与 Telegram 并行调用文章生成接口，不再自动调用微信测试号发送接口。

**Tech Stack:** Python 3.12、dataclasses、PostgreSQL、FastAPI、Matplotlib Agg、Bash、pytest、Ruff、Docker Compose。

## Global Constraints

- Telegram 的文案、图片、API、发送状态机和恢复逻辑不得改变。
- 微信测试号 `/send`、`/status`、`/resend` 接口继续保留，但正式每日任务不再自动调用 `/send`。
- 每天新增多少岗位就输出多少，不抽样、不截断、不只展示前 N 条。
- 新增岗位身份固定为 `source + external_id`；标题或薪资变化不得重复计为新增。
- 前一日同口径快照缺失时显示“基线建立中”，不得把当天全部岗位称为新增。
- `detail_url` 通过岗位身份联查 `core.jobs`，不增加数据库 migration，不在快照表重复保存链接。
- 只展示现有真实字段；不新增招聘人数、报名时间、学历、经验或完整岗位描述。
- 公众号正式图文由人工审核和发布；第一版不自动创建草稿、不自动发布、不记录虚假的 `published`。
- 输出固定为 `article.md`、`article.html`、`cover.png`、`trend.png`、`manifest.json`；目录 `0755`，文件 `0644`。
- 真实快照、岗位明细产物、Token、OpenID、AppSecret、Cookie、服务器地址和个人路径不得进入公开仓库。
- OpenJobFlow 提交标题使用自然中文，不加 `feat:`、`fix:`、`docs:` 前缀。
- 未经用户明确授权不得 commit、push、merge 或部署；每个任务结束只做差异和测试审查。

## File Structure

- Modify `src/jobflow/models/snapshot.py`：定义数据库查询与文章编排共享的不可变新增岗位模型。
- Modify `src/jobflow/db/snapshots.py`：查询当前快照相较前日快照新增的岗位并联查详情链接。
- Modify `src/jobflow/reports/multi_keyword_service.py`：按关键词构建新增岗位分组，复用现有趋势口径。
- Modify `src/jobflow/reports/wechat_article.py`：扩展文章数据、Markdown/HTML 和五件套清单。
- Modify `src/jobflow/reports/charts.py`：生成确定性蓝色横向公众号封面。
- Modify `src/jobflow/reports/wechat_service.py`：增加仅生成文章包与读取生成状态的服务，不触发微信网络请求。
- Modify `src/jobflow/api/reports.py`：增加受保护的文章生成与状态接口。
- Modify `ops/daily_update.sh`：把正式微信分支从测试号发送改为文章包生成。
- Modify `docs/guides/wechat-test-account.md`：增加正式公众号人工审核发布步骤与验收边界。
- Modify `docs/project-handoff.md`：实现完成后记录代码、测试与服务器待验收边界，不提前写成已发布。
- Test `tests/db/test_snapshots.py`、`tests/reports/test_multi_keyword_service.py`、`tests/reports/test_wechat_article.py`、`tests/reports/test_wechat_service.py`、`tests/reports/test_charts.py`、`tests/api/test_wechat_reports.py`、`tests/ops/test_daily_update_script.py`。

---

### Task 1: 查询当天新增岗位并联查详情链接

**Files:**
- Modify: `src/jobflow/models/snapshot.py`
- Modify: `src/jobflow/db/snapshots.py:133-194`
- Test: `tests/db/test_snapshots.py`

**Interfaces:**
- Consumes: 当前快照 ID、前日同口径快照 ID、搜索关键词。
- Produces: `NewJobPosting` 与 `list_new_job_postings(connection, *, current_snapshot_id: int, previous_snapshot_id: int, keyword: str) -> tuple[NewJobPosting, ...]`。

- [ ] **Step 1: 为新增岗位模型和 SQL 差集写失败测试**

在 `tests/db/test_snapshots.py` 增加测试，使用现有 recording connection/cursor 测试模式，断言 SQL 同时包含身份差集和详情链接联查：

```python
def test_list_new_job_postings_uses_identity_diff_and_core_detail_url():
    rows = [
        (
            "boss_zhipin",
            "job-2",
            "AI Agent 工程师",
            "示例公司",
            "上海",
            "20-35K·14薪",
            20,
            35,
            "K_PER_MONTH",
            14,
            ["Python", "LLM"],
            "https://example.test/jobs/2",
        )
    ]
    connection = ReadConnection(rows)

    result = list_new_job_postings(
        connection,
        current_snapshot_id=20,
        previous_snapshot_id=19,
        keyword="AI Agent",
    )

    sql, params = connection.cursor_instance.executed[0]
    normalized = " ".join(sql.split())
    assert "LEFT JOIN core.job_snapshot_items AS previous" in normalized
    assert "LEFT JOIN core.jobs AS jobs" in normalized
    assert "previous.source IS NULL" in normalized
    assert params == (19, 20, "AI Agent")
    assert result[0].detail_url == "https://example.test/jobs/2"
    assert result[0].skills == ("Python", "LLM")
```

再增加稳定排序和输入校验测试：

```python
def test_list_new_job_postings_requires_distinct_positive_snapshot_ids():
    with pytest.raises(ValueError, match="snapshot ids"):
        list_new_job_postings(Mock(), current_snapshot_id=20, previous_snapshot_id=20, keyword="AI Agent")
```

- [ ] **Step 2: 运行测试并确认失败原因是接口尚不存在**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest tests/db/test_snapshots.py -q
```

Expected: collection FAIL，提示无法导入 `NewJobPosting` 或 `list_new_job_postings`。

- [ ] **Step 3: 实现不可变新增岗位模型**

在 `src/jobflow/models/snapshot.py` 增加：

```python
@dataclass(frozen=True)
class NewJobPosting:
    source: str
    external_id: str
    keyword: str
    title: str
    company: str
    city: str
    salary_text: str | None
    salary_min: int | None
    salary_max: int | None
    salary_unit: str | None
    salary_months: int | None
    skills: tuple[str, ...]
    detail_url: str | None

    @property
    def identity(self) -> tuple[str, str]:
        return self.source, self.external_id
```

必要字段的完整性不在数据库映射时静默修复；文章验证层负责拒绝空 `title/company/city`。

- [ ] **Step 4: 实现差集查询**

在 `src/jobflow/db/snapshots.py` 导入 `NewJobPosting` 并增加：

```python
def list_new_job_postings(
    connection,
    *,
    current_snapshot_id: int,
    previous_snapshot_id: int,
    keyword: str,
) -> tuple[NewJobPosting, ...]:
    if current_snapshot_id <= 0 or previous_snapshot_id <= 0:
        raise ValueError("snapshot ids must be positive")
    if current_snapshot_id == previous_snapshot_id:
        raise ValueError("snapshot ids must be distinct")
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise ValueError("keyword must not be empty")

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            current.source,
            current.external_id,
            current.title,
            current.company,
            current.city,
            current.salary_text,
            current.salary_min,
            current.salary_max,
            current.salary_unit,
            current.salary_months,
            current.skills,
            jobs.detail_url
        FROM core.job_snapshot_items AS current
        LEFT JOIN core.job_snapshot_items AS previous
          ON previous.snapshot_id = %s
         AND previous.source = current.source
         AND previous.external_id = current.external_id
        LEFT JOIN core.jobs AS jobs
          ON jobs.source = current.source
         AND jobs.external_id = current.external_id
        JOIN core.job_snapshots AS snapshot
          ON snapshot.id = current.snapshot_id
        WHERE current.snapshot_id = %s
          AND snapshot.search_keyword = %s
          AND previous.source IS NULL
        ORDER BY current.city, current.title, current.external_id, current.source
        """,
        (previous_snapshot_id, current_snapshot_id, normalized_keyword),
    )
    return tuple(
        NewJobPosting(
            source=row[0],
            external_id=row[1],
            keyword=normalized_keyword,
            title=row[2],
            company=row[3],
            city=row[4],
            salary_text=row[5],
            salary_min=row[6],
            salary_max=row[7],
            salary_unit=row[8],
            salary_months=row[9],
            skills=tuple(row[10] or ()),
            detail_url=row[11],
        )
        for row in cursor.fetchall()
    )
```

- [ ] **Step 5: 运行数据库单元测试并审查差异**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest tests/db/test_snapshots.py -q
git diff --check
git diff -- src/jobflow/models/snapshot.py src/jobflow/db/snapshots.py tests/db/test_snapshots.py
```

Expected: `tests/db/test_snapshots.py` 全部 PASS；差异中没有 migration、真实 URL 或个人路径。未经授权不提交。

---

### Task 2: 按关键词编排新增岗位与基线状态

**Files:**
- Modify: `src/jobflow/reports/wechat_article.py:17-82`
- Modify: `src/jobflow/reports/multi_keyword_service.py:230-376`
- Test: `tests/reports/test_multi_keyword_service.py`
- Test: `tests/reports/test_wechat_article.py`

**Interfaces:**
- Consumes: Task 1 的 `list_new_job_postings` 和现有 `SnapshotHeader`、`KeywordTrend`。
- Produces: `KeywordNewJobs`、扩展后的 `WechatArticleData.new_job_groups`，以及保持签名不变的 `build_multi_keyword_wechat_parts(...) -> tuple[WechatArticleData, bytes]`。

- [ ] **Step 1: 写有基线、无基线和空差集失败测试**

在 `tests/reports/test_multi_keyword_service.py` 增加：

```python
def test_wechat_parts_include_all_new_jobs_in_keyword_order(monkeypatch):
    headers = headers_for(("AI Agent", "Python开发"))
    monkeypatch.setattr(service, "_load_headers", Mock(return_value=(headers, ())))
    monkeypatch.setattr(service, "_validate_shared_scope", Mock())
    monkeypatch.setattr(service, "_build_trends", Mock(return_value=sample_trends()))
    monkeypatch.setattr(service, "get_snapshot", previous_header_lookup(headers))
    new_jobs = Mock(return_value=(posting("AI Agent", "job-2"),))
    monkeypatch.setattr(service, "list_new_job_postings", new_jobs)

    data, _png = service.build_multi_keyword_wechat_parts(
        Mock(), snapshot_date=date(2026, 8, 27), keywords=("AI Agent", "Python开发")
    )

    assert tuple(group.keyword for group in data.new_job_groups) == ("AI Agent", "Python开发")
    assert data.new_job_groups[0].postings[0].external_id == "job-2"
```

另写断言：前日快照不存在时 `postings is None`；存在前日快照但无差集时 `postings == ()`。这两个状态不得混淆。

- [ ] **Step 2: 运行测试确认新增分组字段尚不存在**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest tests/reports/test_multi_keyword_service.py tests/reports/test_wechat_article.py -q
```

Expected: FAIL，提示 `KeywordNewJobs` 或 `new_job_groups` 不存在。

- [ ] **Step 3: 扩展微信文章数据契约**

在 `src/jobflow/reports/wechat_article.py` 增加：

```python
@dataclass(frozen=True)
class KeywordNewJobs:
    keyword: str
    postings: tuple[NewJobPosting, ...] | None

    @property
    def has_baseline(self) -> bool:
        return self.postings is not None
```

在 `WechatArticleData` 最后增加默认字段，避免现有测试号模板构造立即失效：

```python
new_job_groups: tuple[KeywordNewJobs, ...] = ()
```

把 `build_article_data` 增加仅关键字参数：

```python
new_job_groups: tuple[KeywordNewJobs, ...] = ()
```

并原样传入 `WechatArticleData`。现有聚合趋势字段和微信测试号模板字段不删除。

- [ ] **Step 4: 在多关键词服务中加载新增岗位分组**

在 `src/jobflow/reports/multi_keyword_service.py` 增加：

```python
def _load_new_job_groups(
    connection,
    *,
    snapshot_date: date,
    headers: Sequence[SnapshotHeader],
) -> tuple[KeywordNewJobs, ...]:
    groups: list[KeywordNewJobs] = []
    for header in headers:
        previous = get_snapshot(
            connection,
            snapshot_date=snapshot_date - timedelta(days=1),
            search_keyword=header.search_keyword,
        )
        if previous is None or _collection_scope(previous) != _collection_scope(header):
            groups.append(KeywordNewJobs(header.search_keyword, None))
            continue
        postings = list_new_job_postings(
            connection,
            current_snapshot_id=header.id,
            previous_snapshot_id=previous.id,
            keyword=header.search_keyword,
        )
        groups.append(KeywordNewJobs(header.search_keyword, postings))
    return tuple(groups)
```

在 `build_multi_keyword_wechat_parts` 中把结果传给 `build_article_data(new_job_groups=...)`。关键词顺序必须沿用 `normalized` / `headers` 顺序，不能使用集合重排。

- [ ] **Step 5: 运行编排测试与现有 Telegram 报告测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest tests/reports/test_multi_keyword_service.py tests/reports/test_wechat_article.py tests/reports/test_daily_brief.py -q
```

Expected: PASS；Telegram brief 输出断言没有变化。未经授权不提交。

---

### Task 3: 渲染“今日新增岗位”正文、封面与五件套

**Files:**
- Modify: `src/jobflow/reports/charts.py:14-190`
- Modify: `src/jobflow/reports/wechat_article.py:84-215`
- Test: `tests/reports/test_charts.py`
- Test: `tests/reports/test_wechat_article.py`

**Interfaces:**
- Consumes: Task 2 的 `WechatArticleData.new_job_groups` 与现有趋势 PNG。
- Produces: `build_daily_new_jobs_cover_png() -> bytes`、扩展后的 `ArticleManifest` 和 `write_wechat_article(data, trend_png, cover_png, output_dir) -> ArticleManifest`。

- [ ] **Step 1: 写封面尺寸、岗位完整输出和安全转义失败测试**

在 `tests/reports/test_charts.py` 增加：

```python
def test_daily_new_jobs_cover_is_landscape_png():
    image = build_daily_new_jobs_cover_png()
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = png_dimensions(image)
    assert width == 900
    assert height == 383
```

在 `tests/reports/test_wechat_article.py` 构造包含 3 个岗位、空技能、空链接和特殊字符的分组，断言：

```python
assert manifest.files == (
    "article.md",
    "article.html",
    "cover.png",
    "trend.png",
    "manifest.json",
)
assert html.count('class="job-card"') == 3
assert "&lt;示例&gt;" in html
assert 'href="https://example.test/jobs/1"' in html
assert "暂无明确技能标签" in html
assert "今日新增岗位" in html
```

同时把旧的“HTML 中不能出现任何 `https://`”断言改为“远程 URL 只能出现在 `<a href>`，不能出现在 `<img src>`、脚本或样式资源”。

- [ ] **Step 2: 运行测试确认五件套和封面函数尚不存在**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest tests/reports/test_charts.py tests/reports/test_wechat_article.py -q
```

Expected: FAIL，提示封面函数不存在或 manifest 仍为四件套。

- [ ] **Step 3: 使用 Matplotlib 生成确定性封面**

在 `src/jobflow/reports/charts.py` 增加：

```python
def build_daily_new_jobs_cover_png() -> bytes:
    with matplotlib.rc_context(
        {"font.family": _select_font_family(), "axes.unicode_minus": False}
    ):
        fig = plt.figure(figsize=(6, 383 / 150), dpi=150, facecolor="#1738C8")
        try:
            ax = fig.add_axes((0, 0, 1, 1))
            ax.set_facecolor("#1738C8")
            ax.axis("off")
            ax.text(0.08, 0.82, "OPENJOBFLOW", color="#DCE6FF", fontsize=10, weight="bold")
            ax.text(0.5, 0.48, "岗位速递", ha="center", va="center", color="white", fontsize=30, weight="bold")
            output = BytesIO()
            fig.savefig(output, format="png", dpi=150, bbox_inches=None, pad_inches=0)
            return output.getvalue()
        finally:
            plt.close(fig)
```

如果 Matplotlib 输出尺寸因浮点取整不是 `900 × 383`，把 `figsize` 调整为 `(6, 383 / 150)` 并以测试读取的 PNG IHDR 为准，不使用外部图片裁剪工具。

- [ ] **Step 4: 扩展文章验证和 Markdown/HTML 渲染**

增加纯函数：

```python
def _sorted_postings(postings: tuple[NewJobPosting, ...]) -> tuple[NewJobPosting, ...]:
    return tuple(sorted(postings, key=lambda item: (item.city, item.title, item.external_id, item.source)))


def _salary_label(posting: NewJobPosting) -> str:
    return posting.salary_text.strip() if posting.salary_text and posting.salary_text.strip() else "薪资面议"


def _skills_label(posting: NewJobPosting) -> str:
    values = tuple(skill.strip() for skill in posting.skills if skill.strip())
    return "、".join(values) if values else "暂无明确技能标签"
```

`_validate` 必须检查：关键词唯一；岗位身份在单组内唯一；`title/company/city` 去除空白后非空；链接为空可接受，非空链接只允许 `http`/`https` 且必须有主机名；趋势图和封面图都以 PNG 签名开头。

Markdown 与 HTML 都按 `new_job_groups` 输出：

```text
有基线 + 有岗位 → 输出全部岗位卡片
有基线 + 空元组 → 输出“今日暂无新增岗位”
postings is None → 输出“基线建立中”
```

HTML 使用 `html.escape(..., quote=True)` 转义文本和属性；外部链接使用 `target="_blank" rel="noopener noreferrer"`。禁止脚本和远程图片。

- [ ] **Step 5: 扩展 manifest 和原子五件套写入**

把 `ArticleManifest` 扩展为：

```python
@dataclass(frozen=True)
class ArticleManifest:
    report_date: str
    files: tuple[str, ...]
    new_job_count: int
    keyword_counts: tuple[tuple[str, int | None], ...]
    cover_sha256: str
    trend_sha256: str
```

把 `write_wechat_article` 签名改为：

```python
def write_wechat_article(
    data: WechatArticleData,
    trend_png: bytes,
    cover_png: bytes,
    output_dir: Path,
) -> ArticleManifest:
```

五个文件全部写入临时目录后再统一 `chmod 0644`、目录 `chmod 0755`，最后沿用现有备份目录和 `os.replace` 原子替换。`manifest.json` 的 `keyword_counts` 对无基线关键词写 `null`，不能写成 0。

- [ ] **Step 6: 运行渲染、原子替换与权限测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest tests/reports/test_charts.py tests/reports/test_wechat_article.py -q
conda run -n jobflow ruff check src/jobflow/reports/charts.py src/jobflow/reports/wechat_article.py tests/reports/test_charts.py tests/reports/test_wechat_article.py
conda run -n jobflow ruff format --check src/jobflow/reports/charts.py src/jobflow/reports/wechat_article.py tests/reports/test_charts.py tests/reports/test_wechat_article.py
```

Expected: Windows 上功能测试 PASS，POSIX 权限测试保持 1 skipped；Ruff check 和 format check 均通过。未经授权不提交。

---

### Task 4: 增加仅生成文章包的微信服务

**Files:**
- Modify: `src/jobflow/reports/wechat_service.py:29-135`
- Test: `tests/reports/test_wechat_service.py`

**Interfaces:**
- Consumes: Task 2 的 `build_multi_keyword_wechat_parts`、Task 3 的 `build_daily_new_jobs_cover_png` 与 `write_wechat_article`。
- Produces: `generate_wechat_article_from_snapshots(...) -> dict[str, object]` 与 `get_wechat_article_status(...) -> dict[str, object]`。

- [ ] **Step 1: 写“只生成、不联网”和安全状态测试**

增加：

```python
def test_generate_article_from_snapshots_writes_package_without_network(monkeypatch, tmp_path):
    builder = Mock(return_value=(article_data(), PNG))
    writer = Mock(return_value=manifest())
    monkeypatch.setattr(wechat_service, "build_multi_keyword_wechat_parts", builder)
    monkeypatch.setattr(wechat_service, "build_daily_new_jobs_cover_png", Mock(return_value=COVER))
    monkeypatch.setattr(wechat_service, "write_wechat_article", writer)

    result = generate_wechat_article_from_snapshots(
        Mock(), snapshot_date=date(2026, 8, 27), runtime_root=tmp_path
    )

    assert result == {
        "status": "generated",
        "snapshot_date": "2026-08-27",
        "new_job_count": 2,
        "baseline_ready": True,
    }
    writer.assert_called_once()
```

再写 `get_wechat_article_status`：通过 `runtime_root=tmp_path` 隔离测试目录；缺目录返回 `pending`；五件套和 manifest 完整返回 `generated`；manifest 路径或内容不得出现在响应中。

- [ ] **Step 2: 运行测试确认服务接口不存在**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest tests/reports/test_wechat_service.py -q
```

Expected: FAIL，无法导入两个新函数。

- [ ] **Step 3: 实现生成服务**

在 `wechat_service.py` 增加：

```python
ARTICLE_FILES = ("article.md", "article.html", "cover.png", "trend.png", "manifest.json")


def generate_wechat_article_from_snapshots(
    connection,
    *,
    snapshot_date: date,
    runtime_root: Path = Path("runtime"),
) -> dict[str, object]:
    article_data, trend_png = build_multi_keyword_wechat_parts(
        connection, snapshot_date=snapshot_date
    )
    cover_png = build_daily_new_jobs_cover_png()
    output_dir = runtime_root / "reports" / snapshot_date.isoformat() / "wechat"
    manifest = write_wechat_article(article_data, trend_png, cover_png, output_dir)
    return {
        "status": "generated",
        "snapshot_date": snapshot_date.isoformat(),
        "new_job_count": manifest.new_job_count,
        "baseline_ready": all(count is not None for _keyword, count in manifest.keyword_counts),
    }
```

此函数不得检查 `WECHAT_ENABLED`，因为生成本地人工审核包不依赖测试号凭据或网络开关。

- [ ] **Step 4: 实现文件系统状态读取**

状态函数签名固定为：

```python
def get_wechat_article_status(
    *,
    snapshot_date: date,
    runtime_root: Path = Path("runtime"),
) -> dict[str, object]:
```

`get_wechat_article_status` 只读取 `manifest.json` 和五件套文件名，校验 `report_date`、`files`、`new_job_count` 和 `keyword_counts` 类型后返回安全字段。JSON 损坏、日期不匹配或缺少任一文件时返回：

```python
{"status": "pending", "snapshot_date": snapshot_date.isoformat()}
```

不要返回服务器绝对路径、岗位明细、图片哈希或异常原文。

- [ ] **Step 5: 更新现有测试号发送调用并运行服务回归**

`send_wechat_daily_report` 调用 `write_wechat_article` 时补入封面 PNG，但保留原发送、失败、不确定和防重复逻辑。运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest tests/reports/test_wechat_service.py tests/reports/test_wechat_template.py tests/channels/test_wechat_official.py -q
```

Expected: 新生成服务与 V1.3.2 测试号服务全部 PASS。未经授权不提交。

---

### Task 5: 暴露受保护的文章生成和状态 API

**Files:**
- Modify: `src/jobflow/api/reports.py:37-77,215-272`
- Test: `tests/api/test_wechat_reports.py`

**Interfaces:**
- Consumes: Task 4 的生成函数和状态函数。
- Produces: `POST /reports/daily/multi/wechat/article/generate` 与 `GET /reports/daily/multi/wechat/article/status`。

- [ ] **Step 1: 写鉴权、成功响应和脱敏错误失败测试**

在现有 `tests/api/test_wechat_reports.py` 的 `wechat_client` 测试模式旁增加文章生成/状态依赖覆盖 helper，并写：

```python
def test_wechat_article_generate_requires_token_before_db_access(monkeypatch):
    generator = Mock()
    connection_provider = Mock()
    client, app = wechat_article_client(monkeypatch, generator, connection_provider)
    try:
        response = client.post(
            "/reports/daily/multi/wechat/article/generate?snapshot_date=2026-08-27"
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401
    connection_provider.assert_not_called()
    generator.assert_not_called()


def test_wechat_article_generate_returns_safe_result(monkeypatch):
    generator = Mock(return_value={
        "status": "generated",
        "snapshot_date": "2026-08-27",
        "new_job_count": 12,
        "baseline_ready": True,
    })
    client, app = wechat_article_client(monkeypatch, generator)
    try:
        response = client.post(
            "/reports/daily/multi/wechat/article/generate?snapshot_date=2026-08-27",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["new_job_count"] == 12
```

错误映射测试：缺快照和口径异常返回 409 且不泄露关键词、SQL 或路径；文件系统错误返回通用 503。

- [ ] **Step 2: 运行 API 测试确认路由为 404**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest tests/api/test_wechat_reports.py -q
```

Expected: 新路由测试 FAIL，响应为 404。

- [ ] **Step 3: 增加依赖提供器和两个路由**

增加：

```python
def get_wechat_article_generator():
    return generate_wechat_article_from_snapshots


def get_wechat_article_status_reader():
    return get_wechat_article_status
```

同时在 `src/jobflow/api/reports.py` 的导入列表中加入 `MultiKeywordScopeError`、`generate_wechat_article_from_snapshots` 和 `get_wechat_article_status`。路由：

```python
@router.post("/daily/multi/wechat/article/generate", dependencies=[Depends(require_report_token)])
def generate_wechat_daily_article(
    snapshot_date: date,
    connection=Depends(get_connection),
    generator=Depends(get_wechat_article_generator),
):
    try:
        return generator(connection, snapshot_date=snapshot_date)
    except (MultiKeywordSnapshotMissing, MultiKeywordScopeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail="wechat article cannot be generated") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc


@router.get("/daily/multi/wechat/article/status", dependencies=[Depends(require_report_token)])
def wechat_daily_article_status(
    snapshot_date: date,
    status_reader=Depends(get_wechat_article_status_reader),
):
    try:
        return status_reader(snapshot_date=snapshot_date)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc
```

状态读取不需要数据库连接，避免纯文件检查因数据库不可用而失败。

- [ ] **Step 4: 运行 API 全文件测试并检查 OpenAPI 路由**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest tests/api/test_wechat_reports.py -q
conda run -n jobflow python -c "from jobflow.api.app import app; paths=app.openapi()['paths']; assert '/reports/daily/multi/wechat/article/generate' in paths; assert '/reports/daily/multi/wechat/article/status' in paths"
```

Expected: PASS，且响应序列化不含 `token`、`openid`、`appsecret`、`runtime` 绝对路径。未经授权不提交。

---

### Task 6: 将正式每日任务改为 Telegram 发送 + 微信文章生成

**Files:**
- Modify: `ops/daily_update.sh:186-215,360-374`
- Modify: `tests/ops/test_daily_update_script.py:122-131`

**Interfaces:**
- Consumes: Task 5 的文章生成 API。
- Produces: 正式 09:00 任务并行执行 Telegram 自动发送和微信文章包生成。

- [ ] **Step 1: 把现有并行测试改成目标行为并确认失败**

把测试改为：

```python
def test_daily_update_runs_telegram_and_wechat_article_generation_in_parallel() -> None:
    text = read_script()
    assert 'send_multi_keyword_report "$SNAPSHOT_DATE" &' in text
    assert 'generate_wechat_article "$SNAPSHOT_DATE" &' in text
    assert 'wait "$telegram_pid"' in text
    assert 'wait "$wechat_article_pid"' in text
    assert "/reports/daily/multi/wechat/article/generate?snapshot_date=" in text
    assert "/reports/daily/multi/wechat/send?snapshot_date=" not in text
    assert 'allowed = {"generated"}' in text
```

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest tests/ops/test_daily_update_script.py -q
```

Expected: FAIL，因为脚本仍调用测试号 `/send`。

- [ ] **Step 2: 将微信 Shell 函数改为文章生成**

把 `send_wechat_report()` 替换为 `generate_wechat_article()`，保留“Token 只在 API 容器内读取”的安全边界。Python 请求目标改为：

```python
f"http://127.0.0.1:8000/reports/daily/multi/wechat/article/generate?snapshot_date={snapshot_date}"
```

只接受：

```python
allowed = {"generated"}
```

输出只打印日期、生成状态、新增岗位数和基线是否就绪，不打印岗位明细、Token 或绝对路径。

- [ ] **Step 3: 更新并行等待变量和失败汇总**

目标结构：

```bash
send_multi_keyword_report "$SNAPSHOT_DATE" &
telegram_pid=$!
generate_wechat_article "$SNAPSHOT_DATE" &
wechat_article_pid=$!

set +e
wait "$telegram_pid"
telegram_status=$?
wait "$wechat_article_pid"
wechat_article_status=$?
set -e

if [[ "$telegram_status" -ne 0 || "$wechat_article_status" -ne 0 ]]; then
    echo "渠道汇总失败：Telegram=$telegram_status，微信文章=$wechat_article_status" >&2
    exit 1
fi
```

并发失败仍只影响本次 service 退出码，不能调用 Telegram 恢复接口或重新发送 Telegram。

- [ ] **Step 4: 运行 Shell 静态测试和语法检查**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest tests/ops/test_daily_update_script.py -q
docker run --rm -v "${PWD}:/work:ro" bash:5.2 bash -n /work/ops/daily_update.sh
```

Expected: pytest PASS，`bash -n` 退出码 0；脚本中测试号 `/wechat/send` 出现次数为 0。未经授权不提交。

---

### Task 7: 文档、总回归和人工验收交接

**Files:**
- Modify: `docs/guides/wechat-test-account.md`
- Modify: `docs/project-handoff.md`
- Modify: `docs/development/README.md`
- Test: `tests/docs/test_public_assets.py`

**Interfaces:**
- Consumes: Tasks 1-6 的最终接口、文件清单和运行边界。
- Produces: 对外可复现的人工发布说明、准确的项目停点和完整验证记录。

- [ ] **Step 1: 更新文档测试的目录入口断言**

在 `tests/docs/test_public_assets.py` 的 development 文档索引测试中加入：

```python
assert (
    DEVELOPMENT_ROOT
    / "specs"
    / "2026-08-27-v1-3-3-wechat-daily-new-jobs-article-design.md"
).is_file()
assert (
    DEVELOPMENT_ROOT
    / "plans"
    / "2026-08-27-v1-3-3-wechat-daily-new-jobs-article.md"
).is_file()
```

并要求 `docs/development/README.md` 包含两个相对链接。

- [ ] **Step 2: 更新微信指南与开发索引**

`docs/guides/wechat-test-account.md` 增加“V1.3.3 正式图文人工发布”章节，准确写出：

```text
检查 runtime/reports/<日期>/wechat/ 五件套
→ 打开 article.html
→ 核对 manifest 数量
→ 上传 cover.png
→ 标题填写“今日新增岗位”
→ 复制正文并人工发布
→ 手机确认图文卡片和岗位详情链接
```

说明测试号模板消息和正式公众号图文卡片不是同一种消息；公开文档只使用 `<JOBFLOW_DIR>`、`YYYY-MM-DD` 和变量名占位符。

在 `docs/development/README.md` 增加本设计和计划的入口链接。

- [ ] **Step 3: 更新交接状态但不提前写生产验收**

`docs/project-handoff.md` 在本机实现完成后记录：

```text
V1.3.3 代码与离线测试完成
五件套本机生成通过
Telegram 回归通过
Ubuntu 真实快照生成与正式公众号发布待用户执行
```

不得在手机端真实发布前写“V1.3.3 已正式验收”。

- [ ] **Step 4: 运行定向测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest tests/db/test_snapshots.py tests/reports/test_multi_keyword_service.py tests/reports/test_charts.py tests/reports/test_wechat_article.py tests/reports/test_wechat_service.py tests/api/test_wechat_reports.py tests/ops/test_daily_update_script.py tests/docs/test_public_assets.py -q
```

Expected: 所有定向测试 PASS；Windows 仅保留明确标记的 POSIX 权限测试 skip。

- [ ] **Step 5: 运行非 integration 总回归和 Ruff**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
conda run -n jobflow python -m pytest -q --ignore=tests/integration
conda run -n jobflow ruff check .
conda run -n jobflow ruff format --check .
git diff --check
```

Expected: 离线回归 PASS，Ruff check 和 `git diff --check` 通过；Ruff format check 单独报告当前基线和本次文件结果，不把 Ruff check 等同于 format check。`tests/integration/` 当前未统一标记 marker，因此使用目录级 `--ignore`，不要用无法真正排除该目录的 `-m "not integration"`。

- [ ] **Step 6: 运行公开仓库安全审查**

Run:

```powershell
git status --short --branch
git diff --name-only
git diff
rg -n -i "(token|password|appsecret|openid|cookie|webhook)" README.md README.zh-CN.md docs src tests ops
```

Expected: 搜索结果只能是变量名、通用说明、测试假值或已审查的历史公开文档；`test_public_assets.py` 继续负责扫描绝对路径、私网地址和已知密钥格式；不得出现真实值、真实服务器地址或个人本机路径。确认 `data/`、`runtime/`、`.env` 和真实岗位产物均未跟踪。

- [ ] **Step 7: 用户授权前停在可审查工作区**

输出最终文件清单、测试结果、未完成的 Ubuntu 步骤和建议提交标题：

```text
添加微信每日新增岗位公告
```

不要执行 `git add`、`git commit`、`git push`、PR、merge 或 Ubuntu 部署。只有用户明确授权后，才按 GitHub Flow 从功能分支提交和推送。

## Final Self-Review Checklist

- [x] 设计文档第 1-17 节均能映射到 Task 1-7。
- [x] 全文不存在 `TBD`、`TODO`、“类似处理”或没有代码/命令的实现占位语句。
- [x] `NewJobPosting`、`KeywordNewJobs`、`WechatArticleData.new_job_groups`、`ArticleManifest` 的字段名在所有任务中一致。
- [x] `write_wechat_article` 的四参数签名在文章服务和测试中一致。
- [x] 新 API 路径在服务、API、Shell 和测试中一致。
- [x] 测试号接口保留，但正式 Shell 不再引用 `/wechat/send`。
- [x] Telegram 现有发送与恢复代码没有列入修改文件。
- [x] 计划没有新增 migration、自动发布接口或公众号文章 URL 回填接口。
- [x] 所有 commit、push 和部署动作均等待用户明确授权。
