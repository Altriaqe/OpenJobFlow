# 微信岗位明文链接实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将微信公众号岗位卡片中的外部超链接改为保存草稿后仍可见、可复制的完整明文网址。

**Architecture:** 保留 `NewJobPosting.detail_url` 的数据来源和现有 URL 校验，只修改公众号 Markdown 与 HTML 两个渲染出口。Markdown 输出“岗位原始地址（复制后打开）”标签和原始网址，HTML 输出经过转义的普通文字；Telegram 链路不改。

**Tech Stack:** Python 3.12、pytest、标准库 `html`、Ruff、Markdown、静态 HTML

## Global Constraints

- 只调整微信公众号文章的 Markdown 和 HTML 输出。
- Telegram 推送内容、岗位抓取、ETL、排序、统计和定时任务保持不变。
- 不建设 GitHub Pages、独立岗位网页、小程序或新的公网服务。
- 不改变现有动态摘要、岗位分隔线、学历显示规则和文章结尾。
- 只接受包含有效主机名的 `http` 或 `https` 地址。
- 不写入 Token、Cookie、服务器地址或其他个人配置。
- 未获得用户明确授权前，不创建 Git commit，不推送远端。

---

### Task 1: 用测试固定公众号明文网址契约

**Files:**
- Modify: `tests/reports/test_wechat_article.py`

**Interfaces:**
- Consumes: `write_wechat_article(data, trend_png, cover_png, output_dir) -> ArticleManifest`
- Produces: Markdown 和 HTML 明文网址行为的回归测试

- [ ] **Step 1: 将 Markdown 断言改为明文网址**

在 `test_markdown_uses_official_account_compatible_job_blocks` 中用以下断言替换旧的 Markdown 超链接断言：

```python
assert "岗位原始地址（复制后打开）：\nhttps://example.test/jobs/1" in markdown
assert markdown.count("岗位原始地址（复制后打开）：\nhttps://example.test/jobs/") == 3
assert "[查看岗位详情 →](" not in markdown
```

- [ ] **Step 2: 将 HTML 断言改为普通文字**

在 `test_html_has_no_script_remote_resource_or_sensitive_fields` 中用以下断言替换旧的 `href` 断言：

```python
assert "岗位原始地址（复制后打开）：<br>https://example.test/jobs/1" in html
assert html.count("岗位原始地址（复制后打开）：<br>https://example.test/jobs/") == 3
assert 'href="https://example.test/jobs/' not in html
```

- [ ] **Step 3: 添加无链接岗位测试**

新增测试，证明 `detail_url=None` 时不会产生空标签：

```python
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
```

- [ ] **Step 4: 运行定向测试，确认当前实现失败**

Run:

```powershell
conda run -n jobflow pytest tests/reports/test_wechat_article.py -q
```

Expected: FAIL，失败点显示当前输出仍为 `[查看岗位详情 →](...)` 和 `<a href=...>`。

---

### Task 2: 将 Markdown 与 HTML 链接改为明文网址

**Files:**
- Modify: `src/jobflow/reports/wechat_article.py:253-254`
- Modify: `src/jobflow/reports/wechat_article.py:282-289`
- Modify: `src/jobflow/reports/wechat_article.py:317-322`
- Test: `tests/reports/test_wechat_article.py`

**Interfaces:**
- Consumes: `NewJobPosting.detail_url: str | None` 和 `_validate` 已验证的 URL
- Produces: `_build_markdown(data, include_title=True) -> str` 与 `_build_html(data) -> str` 的明文网址输出

- [ ] **Step 1: 修改 Markdown 渲染**

将岗位地址的 Markdown 生成逻辑改为：

```python
if posting.detail_url:
    lines.extend(["", "岗位原始地址（复制后打开）：", posting.detail_url])
```

不要使用 `[]()` 链接语法，也不要改变岗位字段顺序和分隔线逻辑。

- [ ] **Step 2: 修改 HTML 渲染**

将 HTML 中的 `link` 构造改为普通段落：

```python
job_url = ""
if posting.detail_url:
    url = html.escape(posting.detail_url, quote=True)
    job_url = f'<p class="job-url">岗位原始地址（复制后打开）：<br>{url}</p>'
```

在岗位卡片拼接处使用：

```python
f"{job_url}</article>"
```

- [ ] **Step 3: 清理失效的链接样式并保证长网址换行**

将原来的 `a{...}` 样式替换为：

```python
"font-weight:700;white-space:nowrap}.company{font-weight:600}.job-url{overflow-wrap:anywhere}"
```

这只负责长网址换行，不制造可点击链接。

- [ ] **Step 4: 运行定向测试**

Run:

```powershell
conda run -n jobflow pytest tests/reports/test_wechat_article.py -q
```

Expected: `tests/reports/test_wechat_article.py` 全部 PASS。

---

### Task 3: 同步说明并完成项目验证

**Files:**
- Modify: `docs/guides/wechat-test-account.md`
- Modify: `docs/development/learning-notes.md`
- Reference: `docs/development/specs/2026-08-28-wechat-plain-job-url-design.md`

**Interfaces:**
- Consumes: Task 2 已通过测试的公众号明文网址行为
- Produces: 与真实公众号限制一致的操作说明和验证记录

- [ ] **Step 1: 更新测试号指南**

在外链限制说明中明确记录：

```markdown
个人公众号保存草稿时可能清除岗位外部超链接。OpenJobFlow 的公众号文章因此直接展示完整岗位网址，不依赖 Markdown 超链接；网址至少应在保存草稿后保持可见并可复制。
```

- [ ] **Step 2: 更新学习记录**

记录本次决策：公众号平台权限属于发布层限制，解决位置应在 WeChat 渲染器，而不是修改抓取数据或 Telegram 渠道。

- [ ] **Step 3: 运行完整测试和静态检查**

Run:

```powershell
conda run -n jobflow pytest -q
conda run -n jobflow ruff check .
conda run -n jobflow ruff format --check .
```

Expected: 完整测试通过；`ruff check .` 通过；`ruff format --check .` 通过。

- [ ] **Step 4: 检查改动边界和敏感信息**

Run:

```powershell
git diff --check
git diff -- src/jobflow/reports/wechat_article.py tests/reports/test_wechat_article.py docs/guides/wechat-test-account.md docs/development/learning-notes.md
git status --short
```

Expected: 无空白错误；只有公众号渲染、对应测试和说明发生相关变化；没有 Token、Cookie、OpenID、AppSecret 或服务器地址值。

- [ ] **Step 5: 生成小样并由用户在公众号保存草稿后复测**

使用现有文章包生成入口重新生成公众号 Markdown，小样至少包含一个有 `detail_url` 的岗位和一个无 `detail_url` 的岗位。人工验收：导入公众号、保存草稿后，完整网址仍存在；无链接岗位不出现“岗位原始地址”。

- [ ] **Step 6: 获得授权后再提交和推送**

只有用户明确授权时才执行：

```powershell
git add src/jobflow/reports/wechat_article.py tests/reports/test_wechat_article.py docs/guides/wechat-test-account.md docs/development/learning-notes.md docs/development/specs/2026-08-28-wechat-plain-job-url-design.md docs/development/plans/2026-08-28-wechat-plain-job-url.md
git commit -m "公众号岗位改用明文链接"
git push origin main
```

Expected: 提交信息为自然中文；推送前再次确认分支为 `main`，且没有夹带无关文件。
