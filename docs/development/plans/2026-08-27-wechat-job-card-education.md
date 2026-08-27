# 微信新增岗位卡片学历展示实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从现有岗位 `skills` 标签识别学历，并在微信公众号 HTML 和 Markdown 岗位卡片中展示学历要求。

**Architecture:** 学历识别只存在于微信文章生成层，由一个纯函数将 `NewJobPosting.skills` 转换为规范化学历和过滤后的技能文本。数据库、快照模型、抓取器、Telegram 和文章包结构均保持不变。

**Tech Stack:** Python 3.12、dataclasses、pytest、Ruff、静态 HTML/Markdown

## Global Constraints

- 只修改微信公众号文章包中的岗位卡片。
- 识别范围固定为：`学历不限`、`中专`、`高中`、`大专`、`本科`、`硕士`、`博士`。
- “统招本科”等包含明确学历词的标签规范化为对应学历。
- 多个学历标签同时存在时，展示原始顺序中的第一个识别结果，并从技能文本移除全部学历标签。
- 识别不到学历时隐藏学历行。
- 学历标签移除后没有剩余技能时，显示“暂无明确技能标签”。
- 不修改抓取规则、数据库、每日快照、`NewJobPosting`、Telegram、文章包文件名、权限或清单结构。
- 不推测原始数据没有提供的学历。
- Git 提交信息使用自然中文，不使用 `feat:`、`fix:`、`docs:` 前缀，不加入助手名字。
- 未获得用户明确授权前，不提交、不推送。

---

## 文件结构

- Modify: `src/jobflow/reports/wechat_article.py` — 识别学历、过滤技能，并渲染 HTML/Markdown 学历行。
- Modify: `tests/reports/test_wechat_article.py` — 覆盖学历识别、缺失值、多个学历标签、技能兜底和双格式输出。
- Existing spec: `docs/development/specs/2026-08-27-wechat-job-card-education-design.md` — 已批准的设计边界。
- This plan: `docs/development/plans/2026-08-27-wechat-job-card-education.md` — 实施和验收步骤。

### Task 1: 增加纯学历识别与技能过滤函数

**Files:**
- Modify: `tests/reports/test_wechat_article.py`
- Modify: `src/jobflow/reports/wechat_article.py`

**Interfaces:**
- Consumes: `NewJobPosting.skills: tuple[str, ...]`
- Produces: `_requirement_labels(posting: NewJobPosting) -> tuple[str | None, str]`，依次返回可选学历显示值和技能显示值。

- [ ] **Step 1: 在测试文件导入纯函数**

把 `tests/reports/test_wechat_article.py` 的文章模块导入补充为：

```python
from jobflow.reports.wechat_article import (
    KeywordNewJobs,
    WechatArticleData,
    _requirement_labels,
    build_article_data,
    write_wechat_article,
)
```

- [ ] **Step 2: 写入失败的学历识别参数化测试**

在 `posting` 测试辅助函数之后加入：

```python
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
```

- [ ] **Step 3: 运行单测并确认因函数不存在而失败**

Run:

```powershell
python -m pytest -q tests/reports/test_wechat_article.py::test_requirement_labels_extract_education_and_filter_skills
```

Expected: collection 失败，错误包含 `cannot import name '_requirement_labels'`。

- [ ] **Step 4: 实现最小纯函数**

在 `src/jobflow/reports/wechat_article.py` 的 `_salary_label` 后、`_new_job_count` 前，用以下代码替换现有 `_skills_label`：

```python
_EDUCATION_LABELS = ("学历不限", "中专", "高中", "大专", "本科", "硕士", "博士")


def _education_label(value: str) -> str | None:
    """把包含明确学历词的岗位标签规范化为学历显示值。"""
    for label in _EDUCATION_LABELS:
        if label in value:
            return label
    return None


def _requirement_labels(posting: NewJobPosting) -> tuple[str | None, str]:
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
    return education, "、".join(skills) or "暂无明确技能标签"
```

- [ ] **Step 5: 运行识别测试并确认通过**

Run:

```powershell
python -m pytest -q tests/reports/test_wechat_article.py::test_requirement_labels_extract_education_and_filter_skills
```

Expected: `5 passed`。

### Task 2: 将学历结果接入 Markdown 和 HTML 卡片

**Files:**
- Modify: `tests/reports/test_wechat_article.py`
- Modify: `src/jobflow/reports/wechat_article.py`

**Interfaces:**
- Consumes: `_requirement_labels(posting: NewJobPosting) -> tuple[str | None, str]`
- Produces: Markdown 和 HTML 仅在识别到学历时包含 `学历要求：<值>`，技能行不再包含学历标签。

- [ ] **Step 1: 写入失败的双格式渲染测试**

在 `tests/reports/test_wechat_article.py` 的 HTML 安全测试之后加入：

```python
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
```

并在现有 `test_html_has_no_script_remote_resource_or_sensitive_fields` 中补充：

```python
assert "学历要求：" not in html
```

- [ ] **Step 2: 运行两个渲染测试并确认失败**

Run:

```powershell
python -m pytest -q tests/reports/test_wechat_article.py::test_markdown_and_html_render_education_without_repeating_skill_tag tests/reports/test_wechat_article.py::test_html_has_no_script_remote_resource_or_sensitive_fields
```

Expected: 两个测试都因文章尚未渲染“学历要求”而失败。

- [ ] **Step 3: 接入 Markdown 卡片**

在 `_build_markdown` 的岗位循环中，先计算显示值：

```python
for posting in _sorted_postings(group.postings):
    education_label, skills_label = _requirement_labels(posting)
    lines.extend(
        [
            f"#### {posting.title}　{_salary_label(posting)}",
            "",
            posting.company,
            "",
            f"工作地点：{posting.city}",
        ]
    )
    if education_label is not None:
        lines.extend(["", f"学历要求：{education_label}"])
    lines.extend(["", f"技能要求：{skills_label}"])
```

保留该循环后面的详情链接和空行处理不变。

- [ ] **Step 4: 接入 HTML 卡片**

在 `_build_html` 的岗位循环中，构建链接后计算显示值，并把学历行放在工作地点与技能要求之间：

```python
education_label, skills_label = _requirement_labels(posting)
education = (
    f"<p>学历要求：{html.escape(education_label)}</p>"
    if education_label is not None
    else ""
)
cards.append(
    '<article class="job-card">'
    '<div class="job-heading">'
    f"<h4>{html.escape(posting.title)}</h4>"
    f'<span class="salary">{html.escape(_salary_label(posting))}</span>'
    "</div>"
    f'<p class="company">{html.escape(posting.company)}</p>'
    f"<p>工作地点：{html.escape(posting.city)}</p>"
    f"{education}"
    f"<p>技能要求：{html.escape(skills_label)}</p>"
    f"{link}</article>"
)
```

- [ ] **Step 5: 运行两个渲染测试并确认通过**

Run:

```powershell
python -m pytest -q tests/reports/test_wechat_article.py::test_markdown_and_html_render_education_without_repeating_skill_tag tests/reports/test_wechat_article.py::test_html_has_no_script_remote_resource_or_sensitive_fields
```

Expected: `2 passed`。

### Task 3: 完成回归验证和提交前检查

**Files:**
- Verify: `src/jobflow/reports/wechat_article.py`
- Verify: `tests/reports/test_wechat_article.py`
- Verify: `docs/development/specs/2026-08-27-wechat-job-card-education-design.md`
- Verify: `docs/development/plans/2026-08-27-wechat-job-card-education.md`

**Interfaces:**
- Consumes: Task 1 和 Task 2 的最终代码。
- Produces: 可部署但尚未提交的已验证工作树；只有用户明确授权后才提交并推送。

- [ ] **Step 1: 运行微信文章模块测试**

Run:

```powershell
python -m pytest -q tests/reports/test_wechat_article.py tests/reports/test_wechat_service.py
```

Expected: 全部通过，无失败。

- [ ] **Step 2: 运行完整离线回归**

Run:

```powershell
python -m pytest -q --ignore=tests/integration
```

Expected: 全部通过；允许现有的单个 skip 和已知 warning，不允许新增失败。

- [ ] **Step 3: 运行静态检查和格式检查**

Run:

```powershell
python -m ruff check .
python -m ruff format --check src/jobflow/reports/wechat_article.py tests/reports/test_wechat_article.py
git diff --check
```

Expected: 三条命令均以退出码 `0` 完成。只检查本次修改的 Python 文件，避免触碰仓库中历史格式问题。

- [ ] **Step 4: 审查最终差异和分支状态**

Run:

```powershell
git diff -- src/jobflow/reports/wechat_article.py tests/reports/test_wechat_article.py docs/development/specs/2026-08-27-wechat-job-card-education-design.md docs/development/plans/2026-08-27-wechat-job-card-education.md
git status --short --branch
```

Expected: 当前为 `main`，只出现上述四个预期文件；不包含 `.env`、runtime、真实岗位数据或个人配置。

- [ ] **Step 5: 等待用户明确授权后提交并直接推送 main**

未授权时停止在此步骤。获得用户明确授权后执行：

```powershell
git add src/jobflow/reports/wechat_article.py tests/reports/test_wechat_article.py docs/development/specs/2026-08-27-wechat-job-card-education-design.md docs/development/plans/2026-08-27-wechat-job-card-education.md
git commit -m "增加微信岗位卡片学历要求"
git push origin main
```

Expected: 提交成功，`origin/main` 指向新提交；提交信息无英文前缀且不包含助手名字。

### Task 4: Ubuntu 部署与真实文章包复验

**Files:**
- Deploy directory: `<DEPLOY_DIR>`，由部署者替换为自己的 OpenJobFlow 部署目录。
- Generated package: `<DEPLOY_DIR>/runtime/reports/2026-08-27/wechat`

**Interfaces:**
- Consumes: 用户授权并推送后的 `origin/main`。
- Produces: Ubuntu 新镜像和重新生成的真实微信文章包，不自动发布公众号。

- [ ] **Step 1: 用户在 Ubuntu 拉取并重建 API**

Run on Ubuntu:

```bash
cd <DEPLOY_DIR>
git pull --ff-only origin main
docker compose build api
docker compose up -d --no-deps api
```

Expected: 镜像构建成功，API 容器重新创建。

- [ ] **Step 2: 等待 API 健康**

Run:

```bash
for i in $(seq 1 20); do
    if curl --noproxy '*' -fsS http://127.0.0.1:8000/health; then
        echo
        break
    fi
    echo "API 启动中：$i/20"
    sleep 3
done
curl --noproxy '*' -fsS http://127.0.0.1:8000/ready
echo
docker compose ps
```

Expected: `/health` 返回 `{"status":"ok"}`，`/ready` 返回 `{"status":"ready"}`，API 和 PostgreSQL 均为 `healthy`。

- [ ] **Step 3: 重新生成 2026-08-27 文章包**

Run:

```bash
docker compose exec -T api python - "2026-08-27" <<'PY'
import json
import os
import sys
import urllib.request

snapshot_date = sys.argv[1]
token = os.environ["REPORT_TRIGGER_TOKEN"]
request = urllib.request.Request(
    f"http://127.0.0.1:8000/reports/daily/multi/wechat/article/generate?snapshot_date={snapshot_date}",
    method="POST",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(request, timeout=120) as response:
    print(json.dumps(json.load(response), ensure_ascii=False, indent=2))
PY
```

Expected: 返回 `status=generated`、`snapshot_date=2026-08-27`、`new_job_count=247`、`baseline_ready=true`，且不会打印 Token。

- [ ] **Step 4: 检查真实文章学历行**

Run:

```bash
REPORT_DIR="runtime/reports/2026-08-27/wechat"
grep -o '学历要求：[^<]*' "$REPORT_DIR/article.html" | sort | uniq -c
grep -n '学历要求：本科' "$REPORT_DIR/article.md" | head
stat -c '%a %n' "$REPORT_DIR" "$REPORT_DIR"/*
```

Expected: 如果当天新增岗位包含可识别学历，则显示规范化结果；无法识别的岗位不包含学历行。目录为 `755`，五个文件均为 `644`。

- [ ] **Step 5: 人工打开文章并确认公众号排版**

把 `wechat` 文件夹下载到 Windows，打开 `article.html`，检查学历行位于“工作地点”和“技能要求”之间，并确认详情链接仍能打开原始招聘页面。

Expected: HTML 视觉验收通过；本步骤只验收文章包，不自动发布微信公众号，也不改变 Telegram。
