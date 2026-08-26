# JobFlow V1.3.1 Multi-Keyword Trend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变四城市、每城三页规则的前提下，为四个岗位关键词建立独立每日快照，并通过 Telegram 发送一份合并趋势简报和一张关键词城市热力图。

**Architecture:** 复用现有 `core.job_snapshots`、`core.job_snapshot_items` 和 `ops.report_deliveries`，不新增数据库迁移。新增一个多关键词报告服务负责装载四份快照、计算同关键词前日趋势、同步四份投递状态；旧的单关键词日报接口保持兼容。每日 Shell 脚本先检查每个关键词快照，只补缺失项，最后调用一次合并发送接口。

**Tech Stack:** Python 3.12、FastAPI、PostgreSQL、psycopg、Matplotlib、pytest、Bash、Docker Compose、systemd、Telegram Bot API。

## Global Constraints

- 固定关键词：`AI Agent`、`Python开发`、`Java开发`、`数据分析`，顺序不可变。
- 固定城市：上海、北京、杭州、深圳，顺序不可变。
- 每个“关键词 × 城市”抓取 3 页，不抓详情页。
- 数据只能表述为固定范围抓取样本或样本需求信号，不得表述为全市场岗位总量。
- 同一岗位可以命中多个关键词；只在单个关键词快照内部按 `source + external_id` 去重。
- 四份快照缺少任何一份时，不发送合并简报。
- 首日没有完整前日基线时发送“趋势基线建立中”提示图，不生成虚假增减热力图。
- 文字成功、图片失败时只补图片；完成后返回 `already_sent`。
- 保留旧的 `/reports/daily/status` 和 `/reports/daily/send` 单关键词接口。
- 不新增数据库表或迁移，不改变 systemd 45 分钟超时。
- 不输出或记录 `.env`、Token、Cookie、订阅、代理节点或其他秘密值。
- 所有 commit 和 push 都是独立授权门；计划中的提交命令不得在未获用户明确授权时执行。

---

## File Map

- Modify `src/jobflow/models/snapshot.py`：增加多关键词趋势的只读数据类型。
- Modify `src/jobflow/reports/comparison.py`：计算每个城市相较前日新增的岗位身份数量。
- Modify `src/jobflow/reports/daily_brief.py`：生成一条合并的多岗位中文简报。
- Modify `src/jobflow/reports/charts.py`：生成热力图和首日基线提示图。
- Create `src/jobflow/reports/multi_keyword_service.py`：装载四份快照、校验范围、同步投递状态并发送一次图文。
- Modify `src/jobflow/reports/daily_service.py`：把周趋势加载函数改为可复用的公开包内函数，旧服务行为不变。
- Modify `src/jobflow/api/reports.py`：增加合并日报状态和发送接口。
- Modify `ops/daily_update.sh`：循环四关键词，只补缺失快照，最后发送合并简报。
- Modify `tests/reports/test_comparison.py`：新增城市新增岗位计数测试。
- Modify `tests/reports/test_daily_brief.py`：新增合并简报测试。
- Modify `tests/reports/test_charts.py`：新增热力图和基线提示图测试。
- Create `tests/reports/test_multi_keyword_service.py`：新增聚合、失败恢复和幂等测试。
- Modify `tests/reports/test_daily_service.py`：覆盖周趋势函数重命名后的兼容性。
- Modify `tests/api/test_reports.py`：新增合并接口鉴权与错误映射测试。
- Modify `tests/ops/test_daily_update_script.py`：更新四关键词脚本契约。
- Modify `README.md`、`docs/reference/architecture.md`、`docs/guides/ubuntu-deployment.md`、`docs/project-handoff.md`：只按实际测试与服务器验收结果更新。

---

### Task 1: 城市新增岗位比较模型

**Files:**
- Modify: `src/jobflow/models/snapshot.py`
- Modify: `src/jobflow/reports/comparison.py`
- Test: `tests/reports/test_comparison.py`

**Interfaces:**
- Produces: `NamedCount(name: str, count: int)`。
- Produces: `KeywordTrend(keyword: str, daily: DailyComparison, new_by_city: tuple[NamedCount, ...] | None, weekly: WeeklyComparison | None)`。
- Produces: `count_new_jobs_by_city(current, previous, *, cities) -> tuple[NamedCount, ...] | None`。

- [ ] **Step 1: 写城市新增计数失败测试**

在 `tests/reports/test_comparison.py` 增加：

```python
from jobflow.reports.comparison import count_new_jobs_by_city


def test_count_new_jobs_by_city_uses_identity_and_preserves_city_order() -> None:
    previous = (
        item("old-sh", city="上海"),
        item("old-bj", city="北京"),
    )
    current = (
        item("old-sh", city="上海"),
        item("new-sh-1", city="上海"),
        item("new-sh-2", city="上海"),
        item("new-bj", city="北京"),
    )

    result = count_new_jobs_by_city(
        current,
        previous,
        cities=("上海", "北京", "杭州", "深圳"),
    )

    assert result is not None
    assert [(metric.name, metric.count) for metric in result] == [
        ("上海", 2),
        ("北京", 1),
        ("杭州", 0),
        ("深圳", 0),
    ]


def test_count_new_jobs_by_city_returns_none_without_baseline() -> None:
    assert count_new_jobs_by_city((), None, cities=("上海",)) is None
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
pytest tests/reports/test_comparison.py -q
```

Expected: collection fails because `count_new_jobs_by_city` is not defined.

- [ ] **Step 3: 增加只读模型**

在 `src/jobflow/models/snapshot.py` 的 `NamedMetric` 后增加：

```python
@dataclass(frozen=True)
class NamedCount:
    name: str
    count: int

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if self.count < 0:
            raise ValueError("count must not be negative")
```

在 `WeeklyComparison` 后增加：

```python
@dataclass(frozen=True)
class KeywordTrend:
    keyword: str
    daily: DailyComparison
    new_by_city: tuple[NamedCount, ...] | None
    weekly: WeeklyComparison | None = None

    def __post_init__(self) -> None:
        if not self.keyword.strip():
            raise ValueError("keyword must not be empty")
```

- [ ] **Step 4: 实现城市新增计数**

在 `src/jobflow/reports/comparison.py` 导入 `NamedCount`，并增加：

```python
def count_new_jobs_by_city(
    current: Sequence[SnapshotItem],
    previous: Sequence[SnapshotItem] | None,
    *,
    cities: Sequence[str],
) -> tuple[NamedCount, ...] | None:
    ordered_cities = tuple(cities)
    if not ordered_cities or len(set(ordered_cities)) != len(ordered_cities):
        raise ValueError("cities must be non-empty and unique")
    if previous is None:
        return None

    previous_identities = {item.identity for item in previous}
    counts = Counter(
        item.city for item in current if item.identity not in previous_identities
    )
    return tuple(NamedCount(city, counts[city]) for city in ordered_cities)
```

- [ ] **Step 5: 运行定向测试**

Run:

```bash
pytest tests/reports/test_comparison.py -q
```

Expected: all comparison tests pass.

- [ ] **Step 6: 审查并在获授权后提交**

Run before authorization:

```bash
git diff --check
git status --short
```

Commit only after explicit authorization:

```bash
git add src/jobflow/models/snapshot.py src/jobflow/reports/comparison.py tests/reports/test_comparison.py
git commit -m "feat: 增加多关键词城市新增趋势模型"
```

---

### Task 2: 合并多岗位简报

**Files:**
- Modify: `src/jobflow/reports/daily_brief.py`
- Test: `tests/reports/test_daily_brief.py`

**Interfaces:**
- Consumes: `KeywordTrend` from Task 1。
- Produces: `build_multi_keyword_brief(*, report_date, trends, city_count, pages_per_city) -> str`。

- [ ] **Step 1: 写简报失败测试**

增加一个包含四个 `KeywordTrend` 的 fixture，并验证：

```python
def test_build_multi_keyword_brief_shows_keyword_and_city_advantages() -> None:
    report = build_multi_keyword_brief(
        report_date=date(2026, 8, 21),
        trends=multi_keyword_trends(),
        city_count=4,
        pages_per_city=3,
    )

    assert report.startswith("━━━━━━━━━━━━━━━━━━\nJobFlow｜多岗位招聘趋势日报")
    assert "【岗位趋势】" in report
    assert "AI Agent：较昨日新增采集" in report
    assert "新增最多城市：上海" in report
    assert "【城市优势】" in report
    assert "4 个关键词 × 4 个城市 × 每组 3 页" in report
    assert "不代表全市场总量" in report
    assert len(report) <= TELEGRAM_MESSAGE_LIMIT


def test_build_multi_keyword_brief_marks_baseline_pending() -> None:
    report = build_multi_keyword_brief(
        report_date=date(2026, 8, 20),
        trends=multi_keyword_trends(has_baseline=False),
        city_count=4,
        pages_per_city=3,
    )

    assert "趋势基线建立中" in report
    assert "新增最多城市" not in report
```

- [ ] **Step 2: 运行并确认失败**

Run:

```bash
pytest tests/reports/test_daily_brief.py -q
```

Expected: fails because `build_multi_keyword_brief` is missing.

- [ ] **Step 3: 实现合并简报**

在 `src/jobflow/reports/daily_brief.py` 增加以下完整接口；复用现有 `_format_direction`：

```python
def _top_new_city(trend: KeywordTrend) -> tuple[str, int] | None:
    if trend.new_by_city is None:
        return None
    top_count = max((metric.count for metric in trend.new_by_city), default=0)
    leaders = [metric.name for metric in trend.new_by_city if metric.count == top_count]
    return "、".join(leaders), top_count


def build_multi_keyword_brief(
    *,
    report_date: date,
    trends: tuple[KeywordTrend, ...],
    city_count: int,
    pages_per_city: int,
) -> str:
    if not trends:
        raise ValueError("trends must not be empty")
    has_complete_baseline = all(trend.new_by_city is not None for trend in trends)
    lines = [
        "━━━━━━━━━━━━━━━━━━",
        "JobFlow｜多岗位招聘趋势日报",
        f"{report_date.isoformat()}　{_WEEKDAYS[report_date.weekday()]}",
        "━━━━━━━━━━━━━━━━━━",
        "",
        "【岗位趋势】",
    ]
    if not has_complete_baseline:
        lines.append("趋势基线建立中，完成下一自然日采集后生成增减趋势。")
    else:
        for trend in trends:
            leader = _top_new_city(trend)
            if leader is None:
                raise ValueError("complete baseline requires city counts")
            city_names, new_count = leader
            if trend.daily.new_count is None:
                raise ValueError("complete baseline requires new job count")
            lines.append(
                f"• {trend.keyword}：较昨日新增采集 {trend.daily.new_count} 个；"
                f"新增最多城市：{city_names}（{new_count} 个）"
            )

    lines.extend(["", "【城市优势】"])
    if not has_complete_baseline:
        lines.append("• 暂无完整前日基线。")
    else:
        city_names = tuple(metric.name for metric in trends[0].new_by_city or ())
        for city in city_names:
            values = [
                (trend.keyword, next(metric.count for metric in trend.new_by_city or () if metric.name == city))
                for trend in trends
            ]
            best = max(value for _, value in values)
            if best == 0:
                lines.append(f"• {city}：今日暂无新增样本")
            else:
                leaders = "、".join(keyword for keyword, value in values if value == best)
                lines.append(f"• {city}：{leaders}新增样本最多（{best} 个）")

    if report_date.weekday() == 6:
        lines.extend(["", "【周趋势】"])
        if all(trend.weekly is not None for trend in trends):
            for trend in trends:
                lines.append(f"• {trend.keyword}：{_format_direction(trend.weekly.total)}")
        else:
            lines.append("• 周趋势数据不足。")

    lines.extend(
        [
            "",
            "【数据口径】",
            f"{len(trends)} 个关键词 × {city_count} 个城市 × 每组 {pages_per_city} 页",
            "数据表示固定范围抓取样本，不代表全市场总量。",
            "同一岗位可能被多个关键词命中。",
            "",
            "JobFlow｜每日招聘数据快照",
        ]
    )
    report = "\n".join(lines)
    if len(report) > TELEGRAM_MESSAGE_LIMIT:
        raise ValueError("report exceeds Telegram message limit")
    return report
```

- [ ] **Step 4: 运行简报测试**

Run:

```bash
pytest tests/reports/test_daily_brief.py -q
```

Expected: all brief tests pass and old single-keyword output remains unchanged.

- [ ] **Step 5: 审查并在获授权后提交**

```bash
git diff --check
git add src/jobflow/reports/daily_brief.py tests/reports/test_daily_brief.py
git commit -m "feat: 增加多岗位合并趋势简报"
```

Do not execute the commit without explicit authorization.

---

### Task 3: 热力图与基线提示图

**Files:**
- Modify: `src/jobflow/reports/charts.py`
- Test: `tests/reports/test_charts.py`

**Interfaces:**
- Consumes: ordered `tuple[KeywordTrend, ...]` and ordered cities。
- Produces: `build_keyword_city_heatmap_png(trends, *, cities) -> bytes`。
- Produces: `build_baseline_pending_png() -> bytes`。

- [ ] **Step 1: 写图片失败测试**

```python
def test_build_keyword_city_heatmap_png_returns_png() -> None:
    image = build_keyword_city_heatmap_png(
        multi_keyword_trends(),
        cities=("上海", "北京", "杭州", "深圳"),
    )
    assert image.startswith(b"\x89PNG\r\n\x1a\n")


def test_build_keyword_city_heatmap_rejects_missing_baseline() -> None:
    with pytest.raises(ValueError, match="baseline"):
        build_keyword_city_heatmap_png(
            multi_keyword_trends(has_baseline=False),
            cities=("上海", "北京", "杭州", "深圳"),
        )


def test_build_baseline_pending_png_returns_png() -> None:
    image = build_baseline_pending_png()
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
```

- [ ] **Step 2: 运行并确认失败**

```bash
pytest tests/reports/test_charts.py -q
```

Expected: imports fail for the two new chart functions.

- [ ] **Step 3: 实现矩阵校验与两张图**

在 `src/jobflow/reports/charts.py` 增加 `_keyword_city_matrix`，严格使用传入顺序，并用 Matplotlib 原生 `imshow`，不增加 seaborn 依赖：

```python
def _keyword_city_matrix(
    trends: Sequence[KeywordTrend],
    cities: Sequence[str],
) -> tuple[list[str], list[str], list[list[int]]]:
    city_labels = list(cities)
    if not city_labels or len(city_labels) != len(set(city_labels)):
        raise ValueError("cities must be non-empty and unique")
    keyword_labels: list[str] = []
    matrix: list[list[int]] = []
    for trend in trends:
        if trend.new_by_city is None:
            raise ValueError("heatmap requires complete baseline")
        by_city = {metric.name: metric.count for metric in trend.new_by_city}
        if set(by_city) != set(city_labels):
            raise ValueError("trend cities do not match report cities")
        keyword_labels.append(trend.keyword)
        matrix.append([by_city[city] for city in city_labels])
    if not keyword_labels or len(keyword_labels) != len(set(keyword_labels)):
        raise ValueError("keywords must be non-empty and unique")
    return keyword_labels, city_labels, matrix
```

`build_keyword_city_heatmap_png` 使用 `figsize=(8, 6)`、`dpi=150`、`cmap="Blues"`，在每个单元格写入整数，标题为“多岗位城市新增趋势”，底部写“固定范围抓取样本，不代表全市场总量”。`build_baseline_pending_png` 使用同样画布，只居中显示“趋势基线建立中”和“完成下一自然日采集后生成热力图”。两个函数都必须在 `finally` 中 `plt.close(fig)`。

- [ ] **Step 4: 运行图表测试和格式检查**

```bash
pytest tests/reports/test_charts.py -q
ruff check src/jobflow/reports/charts.py tests/reports/test_charts.py
ruff format --check src/jobflow/reports/charts.py tests/reports/test_charts.py
```

Expected: all commands exit 0.

- [ ] **Step 5: 视觉检查本地 PNG**

用一个仅写入临时目录的测试脚本生成两张 PNG，检查中文字体、数字、坐标轴和手机竖屏可读性。临时图片不加入 Git。

- [ ] **Step 6: 在获授权后提交**

```bash
git add src/jobflow/reports/charts.py tests/reports/test_charts.py
git commit -m "feat: 增加岗位城市新增热力图"
```

---

### Task 4: 多关键词聚合与合并投递服务

**Files:**
- Create: `src/jobflow/reports/multi_keyword_service.py`
- Modify: `src/jobflow/reports/daily_service.py`
- Modify: `tests/reports/test_daily_service.py`
- Create: `tests/reports/test_multi_keyword_service.py`

**Interfaces:**
- Produces: `DAILY_KEYWORDS = ("AI Agent", "Python开发", "Java开发", "数据分析")`。
- Produces: `get_multi_keyword_report_status(connection, *, snapshot_date, keywords=DAILY_KEYWORDS) -> dict[str, object]`。
- Produces: `send_multi_keyword_report(connection, *, snapshot_date, keywords=DAILY_KEYWORDS, text_sender=send_telegram_text, photo_sender=send_telegram_photo) -> dict[str, object]`。
- Reuses: `load_weekly_comparison_if_sunday` from `daily_service.py`。

- [ ] **Step 1: 先把周趋势加载函数改为包内公开接口**

在 `daily_service.py` 把 `_load_weekly_comparison_if_sunday` 重命名为 `load_weekly_comparison_if_sunday`，并更新本文件调用。同步更新现有测试 mock 名称，运行：

```bash
pytest tests/reports/test_daily_service.py -q
```

Expected: existing single-keyword tests remain green.

- [ ] **Step 2: 写多关键词状态和缺失快照测试**

在新测试文件覆盖：

```python
def test_status_lists_only_missing_keywords(monkeypatch) -> None:
    arrange_headers(monkeypatch, present=("AI Agent", "Java开发"))
    result = get_multi_keyword_report_status(
        Mock(), snapshot_date=REPORT_DATE, keywords=KEYWORDS
    )
    assert result == {
        "status": "missing_snapshots",
        "snapshot_date": "2026-08-20",
        "present_keywords": ["AI Agent", "Java开发"],
        "missing_keywords": ["Python开发", "数据分析"],
    }


def test_send_refuses_partial_snapshot_set(monkeypatch) -> None:
    arrange_headers(monkeypatch, present=("AI Agent", "Python开发", "Java开发"))
    with pytest.raises(MultiKeywordSnapshotMissing, match="数据分析"):
        send_multi_keyword_report(Mock(), snapshot_date=REPORT_DATE, keywords=KEYWORDS)
```

- [ ] **Step 3: 写聚合趋势测试**

构造四份当天快照和四份前日快照，验证 `compare_daily` 与 `count_new_jobs_by_city` 各调用四次、关键词顺序不变、范围不同时报 `MultiKeywordScopeError`。

- [ ] **Step 4: 写投递幂等测试**

至少覆盖：

```python
def test_send_records_same_message_ids_for_all_snapshots(monkeypatch) -> None:
    connection = arrange_complete_snapshot_set(monkeypatch, delivery_status="pending")
    result = send_multi_keyword_report(
        connection,
        snapshot_date=REPORT_DATE,
        text_sender=Mock(return_value=TelegramReceipt(101, 1)),
        photo_sender=Mock(return_value=TelegramReceipt(202, 1)),
    )
    assert result["status"] == "sent"
    assert result["snapshot_ids"] == [11, 12, 13, 14]
    assert record_text_sent.call_count == 4
    assert record_photo_sent.call_count == 4
    assert connection.commit.call_count == 2


def test_partial_failed_resumes_photo_without_duplicate_text(monkeypatch) -> None:
    connection = arrange_complete_snapshot_set(
        monkeypatch,
        delivery_status="partial_failed",
        text_message_id=101,
    )
    text_sender = Mock()
    send_multi_keyword_report(
        connection,
        snapshot_date=REPORT_DATE,
        text_sender=text_sender,
        photo_sender=Mock(return_value=TelegramReceipt(202, 1)),
    )
    text_sender.assert_not_called()


def test_completed_group_returns_already_sent_without_rendering(monkeypatch) -> None:
    arrange_complete_snapshot_set(
        monkeypatch,
        delivery_status="completed",
        text_message_id=101,
        photo_message_id=202,
    )
    assert send_multi_keyword_report(
        Mock(), snapshot_date=REPORT_DATE
    )["status"] == "already_sent"
```

- [ ] **Step 5: 实现服务装载和范围校验**

在新模块定义：

```python
DAILY_KEYWORDS = ("AI Agent", "Python开发", "Java开发", "数据分析")


class MultiKeywordSnapshotMissing(Exception):
    def __init__(self, missing_keywords: tuple[str, ...]) -> None:
        self.missing_keywords = missing_keywords
        super().__init__(f"missing snapshots: {', '.join(missing_keywords)}")


class MultiKeywordScopeError(Exception):
    pass


class MultiKeywordDeliveryStateError(Exception):
    pass
```

装载当天 header 时按 `keywords` 顺序调用 `get_snapshot`。共同范围只比较：

```python
def _collection_scope(header: SnapshotHeader) -> tuple[tuple[str, ...], int, bool]:
    return tuple(sorted(header.cities)), header.pages_per_city, header.details_included
```

四份 header 的 collection scope 必须相同。

- [ ] **Step 6: 实现趋势聚合**

对每个当天 header：加载当天 items；加载前一自然日同关键词 header；只有 collection scope 相同才加载 previous items。分别计算：

```python
daily = compare_daily(current_items, previous_items, cities=header.cities)
new_by_city = count_new_jobs_by_city(
    current_items,
    previous_items,
    cities=header.cities,
)
weekly = load_weekly_comparison_if_sunday(
    connection,
    report_date=snapshot_date,
    keyword=header.search_keyword,
    current_header=header,
)
trend = KeywordTrend(header.search_keyword, daily, new_by_city, weekly)
```

- [ ] **Step 7: 实现四份投递状态同步**

读取四个 `ReportDelivery`。允许的统一阶段只有：

```text
全部 pending/failed 且均无 message id
全部 text_sent/partial_failed 且 text_message_id 相同
全部 completed 且 text_message_id、photo_message_id 分别相同
```

任何混合阶段都抛出 `MultiKeywordDeliveryStateError`，防止覆盖旧的单关键词投递记录。文本成功后循环调用四次 `record_text_sent` 再统一 commit；图片成功或失败同理。

渲染逻辑：

```python
text = build_multi_keyword_brief(
    report_date=snapshot_date,
    trends=trends,
    city_count=headers[0].city_count,
    pages_per_city=headers[0].pages_per_city,
)
image = (
    build_keyword_city_heatmap_png(trends, cities=headers[0].cities)
    if all(trend.new_by_city is not None for trend in trends)
    else build_baseline_pending_png()
)
```

- [ ] **Step 8: 运行服务回归**

```bash
pytest tests/reports/test_multi_keyword_service.py tests/reports/test_daily_service.py -q
ruff check src/jobflow/reports/multi_keyword_service.py tests/reports/test_multi_keyword_service.py
ruff format --check src/jobflow/reports/multi_keyword_service.py tests/reports/test_multi_keyword_service.py
```

Expected: all commands exit 0.

- [ ] **Step 9: 在获授权后提交**

```bash
git add src/jobflow/reports/multi_keyword_service.py src/jobflow/reports/daily_service.py tests/reports/test_multi_keyword_service.py tests/reports/test_daily_service.py
git commit -m "feat: 增加多关键词合并投递服务"
```

---

### Task 5: 合并日报 API

**Files:**
- Modify: `src/jobflow/api/reports.py`
- Modify: `tests/api/test_reports.py`

**Interfaces:**
- Produces: `GET /reports/daily/multi/status?snapshot_date=YYYY-MM-DD`。
- Produces: `POST /reports/daily/multi/send?snapshot_date=YYYY-MM-DD`。
- Both use existing Bearer `REPORT_TRIGGER_TOKEN` dependency without exposing its value。

- [ ] **Step 1: 写 API 失败测试**

增加依赖覆盖 getter，并验证：

```python
def test_multi_daily_send_forwards_date(monkeypatch) -> None:
    sender = Mock(return_value={"status": "sent", "snapshot_ids": [11, 12, 13, 14]})
    connection = Mock()
    client, app = multi_daily_client(monkeypatch, sender, lambda: connection)
    try:
        response = client.post(
            "/reports/daily/multi/send?snapshot_date=2026-08-20",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    sender.assert_called_once_with(connection, snapshot_date=date(2026, 8, 20))


def test_multi_daily_status_does_not_expose_secrets(monkeypatch) -> None:
    reader = Mock(return_value={
        "status": "missing_snapshots",
        "snapshot_date": "2026-08-20",
        "present_keywords": ["AI Agent"],
        "missing_keywords": ["Python开发", "Java开发", "数据分析"],
    })
    client, app = multi_daily_client(monkeypatch, Mock(), status_reader=reader)
    try:
        response = client.get(
            "/reports/daily/multi/status?snapshot_date=2026-08-20",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "token" not in str(response.json()).lower()
```

- [ ] **Step 2: 运行并确认 404 或 import failure**

```bash
pytest tests/api/test_reports.py -q
```

- [ ] **Step 3: 增加依赖 getter 和路由**

在 `src/jobflow/api/reports.py` 增加：

```python
def get_multi_daily_report_sender():
    return send_multi_keyword_report


def get_multi_daily_status_reader():
    return get_multi_keyword_report_status


@router.get("/daily/multi/status", dependencies=[Depends(require_report_token)])
def multi_daily_report_status(
    snapshot_date: date,
    connection=Depends(get_connection),
    status_reader=Depends(get_multi_daily_status_reader),
):
    try:
        return status_reader(connection, snapshot_date=snapshot_date)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc


@router.post("/daily/multi/send", dependencies=[Depends(require_report_token)])
def send_multi_daily_snapshot_report(
    snapshot_date: date,
    connection=Depends(get_connection),
    report_sender=Depends(get_multi_daily_report_sender),
):
    try:
        return report_sender(connection, snapshot_date=snapshot_date)
    except MultiKeywordSnapshotMissing as exc:
        raise HTTPException(status_code=409, detail="daily snapshots incomplete") from exc
    except TelegramDeliveryError as exc:
        raise HTTPException(status_code=502, detail="report delivery failed") from exc
    except TelegramConfigurationError as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc
```

- [ ] **Step 4: 运行 API 与旧日报回归**

```bash
pytest tests/api/test_reports.py tests/reports/test_daily_service.py -q
```

Expected: new routes pass; old routes remain green.

- [ ] **Step 5: 在获授权后提交**

```bash
git add src/jobflow/api/reports.py tests/api/test_reports.py
git commit -m "feat: 增加多关键词日报接口"
```

---

### Task 6: 每日多关键词抓取脚本

**Files:**
- Modify: `ops/daily_update.sh`
- Modify: `tests/ops/test_daily_update_script.py`

**Interfaces:**
- Consumes existing `GET /reports/daily/status` once per keyword。
- Consumes new `POST /reports/daily/multi/send` once after all snapshots exist。
- Produces four independent ETL snapshots for the same `SNAPSHOT_DATE`。

- [ ] **Step 1: 更新 Shell 契约失败测试**

替换单关键词断言，增加：

```python
def test_daily_update_uses_four_keywords_and_original_scope() -> None:
    text = read_script()
    assert 'KEYWORDS=("AI Agent" "Python开发" "Java开发" "数据分析")' in text
    assert 'CITIES=("上海" "北京" "杭州" "深圳")' in text
    assert 'PAGES=3' in text
    assert 'for keyword in "${KEYWORDS[@]}"' in text
    assert '--keyword "$keyword"' in text
    assert '--search-keyword "$keyword"' in text
    assert '--pages "$PAGES"' in text
    assert "--no-detail" in text


def test_daily_update_checks_each_snapshot_and_sends_one_combined_report() -> None:
    text = read_script()
    assert "/reports/daily/status?snapshot_date=" in text
    assert "/reports/daily/multi/send?snapshot_date=" in text
    assert text.count("/reports/daily/multi/send?snapshot_date=") == 1
    assert "已存在快照，本关键词跳过抓取" in text
```

- [ ] **Step 2: 运行并确认失败**

```bash
pytest tests/ops/test_daily_update_script.py -q
```

- [ ] **Step 3: 重构固定配置和状态函数**

脚本顶部改为：

```bash
KEYWORDS=("AI Agent" "Python开发" "Java开发" "数据分析")
CITIES=("上海" "北京" "杭州" "深圳")
PAGES=3
```

新增 `snapshot_exists`：在 API 容器内读取 `REPORT_TRIGGER_TOKEN`，GET 旧的单关键词状态接口；HTTP 200 返回 0，HTTP 404 返回 10，其他错误返回 1。宿主机不得读取或打印 token：

```bash
snapshot_exists() {
    local snapshot_date="$1"
    local keyword="$2"
    docker compose exec -T api python - "$snapshot_date" "$keyword" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

token = os.getenv("REPORT_TRIGGER_TOKEN")
if not token:
    print("日报状态检查失败：缺少触发凭据", file=sys.stderr)
    raise SystemExit(1)

query = urllib.parse.urlencode(
    {"snapshot_date": sys.argv[1], "keyword": sys.argv[2]}
)
request = urllib.request.Request(
    f"http://127.0.0.1:8000/reports/daily/status?{query}",
    headers={"Authorization": f"Bearer {token}"},
)
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
except urllib.error.HTTPError as exc:
    raise SystemExit(10 if exc.code == 404 else 1) from None
except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
    raise SystemExit(1) from None

if not isinstance(payload, dict) or payload.get("snapshot_date") != sys.argv[1]:
    raise SystemExit(1)
raise SystemExit(0)
PY
}
```

- [ ] **Step 4: 把单关键词采集合并封装为函数**

新增：

```bash
capture_keyword() {
    local keyword="$1"
    local keyword_index="$2"
    local keyword_dir="$WORK_DIR/keyword-$keyword_index"
    mkdir -p "$keyword_dir"

    for city in "${CITIES[@]}"; do
        echo "开始抓取：$keyword / $city"
        "$PYTHON" scripts/boss_cdp_raw.py \
            --keyword "$keyword" \
            --city "$city" \
            --pages "$PAGES" \
            --no-detail \
            --format json \
            --output "$keyword_dir/${city}.json"
    done

    merge_keyword_files "$keyword" "$keyword_index" "$keyword_dir"
    docker compose run --rm etl \
        "/data/raw/inbox/jobflow-keyword-${keyword_index}.json" \
        --snapshot-date "$SNAPSHOT_DATE" \
        --search-keyword "$keyword" \
        --cities "$(IFS=,; echo "${CITIES[*]}")" \
        --pages-per-city "$PAGES" \
        --detail-mode no-detail
}
```

`merge_keyword_files` 复用现有 Python 合并逻辑，每个关键词单独建立 `seen_job_ids`，任一城市返回 0 条时整关键词失败。原子文件名使用 `jobflow-keyword-<index>.json`，避免把中文关键词直接作为路径。

- [ ] **Step 5: 实现只补缺失关键词的主循环**

```bash
missing_count=0
for index in "${!KEYWORDS[@]}"; do
    keyword="${KEYWORDS[$index]}"
    if snapshot_exists "$SNAPSHOT_DATE" "$keyword"; then
        echo "$keyword 已存在快照，本关键词跳过抓取"
        continue
    else
        status=$?
    fi
    if [[ "$status" -ne 10 ]]; then
        echo "$keyword 快照状态不确定，本次停止"
        exit "$status"
    fi
    missing_count=$((missing_count + 1))
    capture_keyword "$keyword" "$index"
done

echo "开始发送 Telegram 多关键词图文简报"
send_multi_keyword_report "$SNAPSHOT_DATE"
echo "JobFlow 多关键词每日更新完成"
```

只在 `missing_count > 0` 时执行一次 BOSS `--check`；如果四份快照都存在，直接恢复合并投递。

- [ ] **Step 6: 运行 Shell 契约与语法检查**

Windows:

```bash
pytest tests/ops/test_daily_update_script.py -q
```

Ubuntu 部署前：

```bash
bash -n ops/daily_update.sh
```

Expected: tests pass and `bash -n` exits 0 without output.

- [ ] **Step 7: 在获授权后提交**

```bash
git add ops/daily_update.sh tests/ops/test_daily_update_script.py
git commit -m "feat: 增加每日多关键词断点采集"
```

---

### Task 7: 全量回归、文档与 Ubuntu 验收

**Files:**
- Modify after verified facts only: `README.md`
- Modify after verified facts only: `docs/reference/architecture.md`
- Modify after verified facts only: `docs/guides/ubuntu-deployment.md`
- Modify after verified facts only: `docs/project-handoff.md`

**Interfaces:**
- Verifies all prior tasks as one end-to-end release candidate。
- Produces evidence for V1.3.1 implementation, first-day baseline delivery, and second-day heatmap delivery。

- [ ] **Step 1: 运行本机定向测试**

```bash
pytest tests/reports/test_comparison.py tests/reports/test_daily_brief.py tests/reports/test_charts.py tests/reports/test_multi_keyword_service.py tests/reports/test_daily_service.py tests/api/test_reports.py tests/ops/test_daily_update_script.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: 运行非 PostgreSQL 全回归和静态检查**

```bash
pytest -q
ruff check .
ruff format --check .
git diff --check
```

如本机缺少 PostgreSQL，明确区分未运行的数据库集成测试，不把它写成通过。

- [ ] **Step 3: 审查提交边界**

```bash
git status --short --branch
git diff --name-status
```

不得纳入 `.env`、真实抓取 JSON、`runtime/` 私有配置、`.superpowers/brainstorm/`、Token、Cookie、Chrome Profile 或知识库。

- [ ] **Step 4: 在获授权后提交代码并推送**

提交信息由用户确认。推送必须再次获得明确授权，不把 commit 授权自动扩大为 push 授权。

- [ ] **Step 5: Ubuntu 部署前只读检查**

由用户在 Ubuntu 执行：

```bash
cd <JOBFLOW_DIR>
git status --short --branch
git log -5 --oneline
systemctl status jobflow-daily-update.timer --no-pager
docker compose -f compose.yaml -f compose.proxy.yaml ps
```

先处理服务器真实未提交内容，不能直接覆盖。

- [ ] **Step 6: 安全部署到下一自然日**

必须避免在当天旧版 `AI Agent` 已完成单关键词投递后混用新的四关键词投递状态。优先在下一自然日首次运行 V1.3.1；部署后先构建并重启 API，再执行 `bash -n ops/daily_update.sh`。

- [ ] **Step 7: 首日真实验收**

确认：

```text
四个关键词均完成四城市 × 三页抓取
四份 core.job_snapshots 记录存在
四份采集范围完全一致
Telegram 收到一份合并文字
Telegram 收到“趋势基线建立中”提示图
脚本退出码 0
总运行时间小于 45 分钟
```

查询数据库时只显示日期、关键词、城市数、页数、状态和岗位数量，不显示原始岗位详情或秘密值。

- [ ] **Step 8: 第二自然日真实验收**

确认 Telegram 收到正式热力图，并抽查至少两个单元格的新增数与数据库中 `source + external_id` 差集一致。只有这一步通过，才能称“趋势热力图真实验收完成”。

- [ ] **Step 9: 按真实结果更新公开文档和交接文档**

文档必须区分：

```text
代码已实现
本机自动化测试已通过
Ubuntu 首日基线已验收
Ubuntu 第二日趋势热力图已验收
连续多日稳定性仍待观察
```

- [ ] **Step 10: 文档自审并在获授权后提交**

```bash
git diff --check
git status --short --branch
```

文档 commit 和 push 均需用户单独授权。

---

## Execution Notes

- V1.3.1 是一个连续实现计划，但每个 Task 都必须独立通过测试和人工审查后才能进入下一项。
- 不允许用四个关键词固定抓取数比较“完整市场需求”；热力图只比较相较前日新增的样本岗位身份。
- 计划实现期间保留旧单关键词服务测试，确保回滚路径仍可用。
- Ubuntu 实际操作由用户亲手执行；本机代码、测试和文档可以由 Codex 完成并逐步解释。
