# 微信草稿内联排版修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让微信公众号自动草稿保留此前确认的摘要卡片、趋势表格、岗位层级、橙色薪资和细分隔线，同时继续由用户人工审核与发布。

**Architecture:** 保留 `WechatArticleData`、Markdown 文件和文章包清单不变，只把 `_build_html` 从完整网页改为微信可保存的内联 HTML 片段。草稿客户端继续替换趋势图 URL，并通过已修复的 UTF-8 JSON 调用 `draft/add`。

**Tech Stack:** Python 3.12、标准库 `html`、pytest、requests、微信公众号草稿 API、Docker Compose。

## Global Constraints

- Telegram、ETL、多关键词统计、数据库幂等和人工正式发布边界不变。
- 不使用 `<style>`、CSS class、JavaScript、远程 CSS、iframe、表单或事件属性。
- 所有岗位业务文本必须继续使用 `html.escape`。
- Markdown 人工包继续生成，自动草稿只消费内联 HTML。
- 不记录或输出真实 AppID、AppSecret、Token、素材 ID、Cookie 或服务器私有配置。
- 任何 Git 提交和推送都等待用户明确授权，提交信息不使用 `feat:`、`fix:` 或 `docs:` 前缀。

---

## File Structure

- `src/jobflow/reports/wechat_article.py`：生成 Markdown 和公众号兼容 HTML；本计划只修改 HTML 渲染实现。
- `tests/reports/test_wechat_article.py`：锁定文章内容、安全转义和微信内联样式契约。
- `tests/reports/test_wechat_draft_service.py`：确认文章 HTML 可以经过趋势图 URL 替换进入草稿 payload。
- `docs/development/specs/2026-08-30-wechat-inline-article-style-design.md`：已确认的设计边界。

### Task 1: 锁定微信可保留的内联 HTML 契约

**Files:**
- Modify: `tests/reports/test_wechat_article.py`
- Test: `tests/reports/test_wechat_article.py`

**Interfaces:**
- Consumes: `write_wechat_article(data, trend_png, cover_png, output_dir) -> ArticleManifest`
- Produces: 对 `article.html` 的微信公众号兼容契约，供 Task 2 实现。

- [ ] **Step 1: 增加失败测试，拒绝微信会清理的全局样式**

在现有文章包测试中读取 `article.html`，增加：

```python
html_text = (output_dir / "article.html").read_text(encoding="utf-8")

for forbidden in (
    "<!doctype",
    "<html",
    "<head",
    "<style",
    "class=",
    "display:flex",
):
    assert forbidden not in html_text.lower()
```

- [ ] **Step 2: 增加失败测试，要求已确认的视觉层级全部使用内联样式**

```python
assert 'style="background:#eef4ff;' in html_text
assert 'style="color:#e05a2a;' in html_text
assert 'style="border-bottom:1px solid #dbe4f0;' in html_text
assert 'style="width:100%;border-collapse:collapse;' in html_text
assert "overflow-wrap:anywhere" in html_text
assert "岗位原始地址（复制后打开）：" in html_text
```

- [ ] **Step 3: 增加安全回归断言**

使用包含 `<script>alert(1)</script>` 的岗位名称和包含 `&` 的公司名生成文章，然后断言：

```python
assert "<script>" not in html_text
assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_text
assert "研发&amp;数据公司" in html_text
assert "javascript:" not in html_text
```

- [ ] **Step 4: 运行测试并确认因旧全局 CSS 实现失败**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests\reports\test_wechat_article.py
```

Expected: 新增断言失败，输出仍含 `<style>`、`class=` 或缺少目标内联样式。

### Task 2: 把文章 HTML 改为公众号兼容片段

**Files:**
- Modify: `src/jobflow/reports/wechat_article.py`
- Test: `tests/reports/test_wechat_article.py`

**Interfaces:**
- Consumes: `_build_html(data: WechatArticleData) -> str` 的现有调用方式。
- Produces: 不含网页外壳和 CSS class、只含内联样式的 HTML 字符串。

- [ ] **Step 1: 定义集中维护的内联样式常量**

在模块常量区加入：

```python
_INLINE = {
    "root": "max-width:760px;margin:0 auto;padding:8px 4px;color:#182230;line-height:1.75;font-size:16px;",
    "summary": "background:#eef4ff;padding:16px;border-radius:12px;margin:16px 0;",
    "section_title": "font-size:20px;font-weight:700;margin:28px 0 12px;color:#182230;",
    "table": "width:100%;border-collapse:collapse;margin:12px 0;table-layout:fixed;",
    "th": "border:1px solid #dbe4f0;padding:8px 6px;background:#f5f7fa;text-align:left;",
    "td": "border:1px solid #dbe4f0;padding:8px 6px;vertical-align:top;",
    "group": "font-size:18px;font-weight:700;margin:26px 0 8px;color:#244a82;",
    "job": "border-bottom:1px solid #dbe4f0;padding:16px 0 18px;margin:0;",
    "job_table": "width:100%;border-collapse:collapse;table-layout:fixed;",
    "title": "font-size:17px;font-weight:700;color:#182230;vertical-align:top;",
    "salary": "font-size:17px;font-weight:700;color:#e05a2a;text-align:right;vertical-align:top;white-space:nowrap;",
    "company": "font-weight:700;margin:8px 0 4px;color:#182230;",
    "line": "margin:4px 0;color:#344054;",
    "url": "margin:8px 0 0;color:#475467;overflow-wrap:anywhere;word-break:break-all;",
    "disclaimer": "margin:28px 0 8px;color:#667085;font-size:13px;line-height:1.7;",
}
```

- [ ] **Step 2: 用内联表格生成趋势区域**

把旧 `rows` 改成：

```python
rows = "".join(
    "<tr>"
    f'<td style="{_INLINE["td"]}">{html.escape(keyword)}</td>'
    f'<td style="{_INLINE["td"]}text-align:right;">{total}</td>'
    f'<td style="{_INLINE["td"]}text-align:right;">'
    f'{"基线建立中" if new_count is None else new_count}</td>'
    "</tr>"
    for keyword, total, new_count in data.keyword_rows
)
```

表头使用三个带 `_INLINE["th"]` 的 `<th>`，整个表格使用 `_INLINE["table"]`。

- [ ] **Step 3: 用两列表格和细线生成岗位区域**

每个岗位生成以下结构，所有业务文本都先 `html.escape`：

```python
cards.append(
    f'<section style="{_INLINE["job"]}">'
    f'<table role="presentation" style="{_INLINE["job_table"]}"><tr>'
    f'<td style="{_INLINE["title"]}">{html.escape(posting.title)}</td>'
    f'<td style="{_INLINE["salary"]}">{html.escape(_salary_label(posting))}</td>'
    "</tr></table>"
    f'<p style="{_INLINE["company"]}">{html.escape(posting.company)}</p>'
    f'<p style="{_INLINE["line"]}">工作地点：{html.escape(posting.city)}</p>'
    f"{education}"
    f'<p style="{_INLINE["line"]}">技能要求：{html.escape(skills_label)}</p>'
    f"{job_url}"
    "</section>"
)
```

`education` 使用 `_INLINE["line"]`；`job_url` 使用 `_INLINE["url"]`，仍然只显示明文地址，不生成外部超链接。

- [ ] **Step 4: 返回正文片段而不是完整网页**

`_build_html` 最终返回：

```python
return (
    f'<section style="{_INLINE["root"]}">'
    f'<h1 style="font-size:24px;margin:8px 0 16px;color:#182230;">{title}</h1>'
    f'<section style="{_INLINE["summary"]}">'
    f"<p style=\"margin:0;\">今日新增岗位：{_new_job_count(data)}<br>"
    f"搜索关键词：{'、'.join(html.escape(row[0]) for row in data.keyword_rows)}<br>"
    f"覆盖城市：{'、'.join(html.escape(city) for city in data.cities)}</p></section>"
    + trend_table_and_sections
    + f'<p style="{_INLINE["disclaimer"]}">{ARTICLE_DISCLAIMER}</p>'
    + "</section>"
)
```

不得拼回 `<doctype>`、`<html>`、`<head>` 或 `<style>`。

- [ ] **Step 5: 运行文章测试**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests\reports\test_wechat_article.py
```

Expected: PASS；现有标题、岗位字段、学历隐藏、Markdown、图片摘要和文件权限测试不回归。

### Task 3: 验证草稿链路并准备真实复测

**Files:**
- Modify: `tests/reports/test_wechat_draft_service.py`
- Verify: `src/jobflow/channels/wechat_draft.py`
- Verify: `ops/daily_update.sh`

**Interfaces:**
- Consumes: `create_wechat_draft_from_article(...) -> DraftResult` 与 UTF-8 `create_draft(...) -> str`。
- Produces: 可在服务器删除错误草稿、清理幂等记录并创建一次新草稿的验收流程。

- [ ] **Step 1: 增加草稿 payload 兼容测试**

让测试文章包含内联样式与 `trend.png`，捕获传入 `create_draft` 的 payload：

```python
captured = {}

def capture_draft(**kwargs):
    captured.update(kwargs["payload"])
    return "draft"

assert "trend.png" not in captured["articles"][0]["content"]
assert "https://img" in captured["articles"][0]["content"]
assert 'style="' in captured["articles"][0]["content"]
assert "<style" not in captured["articles"][0]["content"]
```

- [ ] **Step 2: 运行微信、API、脚本和非集成回归**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest -q --ignore=tests\integration
ruff check src tests
git diff --check
```

Expected: 所有非集成测试通过；仅允许已有 POSIX 权限测试在 Windows 跳过；Ruff 和差异检查通过。

- [ ] **Step 3: 用户授权后提交和推送**

```powershell
git add src/jobflow/reports/wechat_article.py `
  tests/reports/test_wechat_article.py `
  tests/reports/test_wechat_draft_service.py `
  docs/development/specs/2026-08-30-wechat-inline-article-style-design.md `
  docs/development/plans/2026-08-30-wechat-inline-article-style.md
git commit -m "修复微信公众号草稿文章排版"
git push origin main
```

Expected: `origin/main` 指向新提交，本地工作区干净。

- [ ] **Step 4: 服务器拉取、重建和真实草稿验收**

服务器先确认只有预期的 `compose.proxy.yaml` 历史本地修改；远端已包含动态 `NO_PROXY` 修复后，再恢复该文件并拉取。重建 API 后，使用数据库保存的 `draft_media_id` 调用 `/cgi-bin/draft/delete` 删除当前错误草稿；只有微信返回 `errcode=0` 才删除 `ops.wechat_draft_jobs` 对应日期记录。

随后调用受保护的：

```text
POST /reports/daily/multi/wechat/draft/create?snapshot_date=2026-08-29
```

Expected:

```json
{"snapshot_date":"2026-08-29","status":"created","has_draft":true,"error_code":null}
```

- [ ] **Step 5: 后台人工预览验收**

确认：中文正常、浅蓝摘要卡片存在、趋势表格有边框、趋势图正常、关键词分组清晰、岗位名称与橙色薪资同排、公司名加粗、岗位间细线存在、明文链接可复制、免责声明完整。未明确通过前不正式发布。

## Self-Review Result

- Spec coverage: 视觉目标、HTML 兼容、安全转义、Markdown 兜底、Telegram 隔离、失败语义和真实验收均有对应步骤。
- 占位符扫描：通过，所有代码改动与命令均给出具体内容。
- Type consistency: 保持 `_build_html(data) -> str`、`write_wechat_article(...) -> ArticleManifest` 和 `create_wechat_draft_from_article(...) -> DraftResult` 现有接口，不新增跨模块类型。
