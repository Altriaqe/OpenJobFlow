# 微信公众号 Markdown 岗位分隔排版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 OpenJobFlow 生成动态命名的公众号导入 Markdown，正确显示图文标题、岗位名称、薪资和公司，并用细分隔线区分相邻岗位。

**Architecture:** 保留现有 `WechatArticleData`、文章包结构和 HTML 预览，只调整 `_build_markdown` 的单岗位文本结构。岗位名称与薪资改为同一粗体普通段落，公司改为粗体普通段落，相邻岗位之间插入 Markdown 水平线 `---`；先由单元测试固定格式，再生成 3 岗位小样进行公众号真实导入验收。

**Tech Stack:** Python 3.12、标准 Markdown、pytest、Ruff、微信公众号 Markdown 导入器。

## Global Constraints

- 只修改微信公众号文章包和 Markdown 展示格式。
- Telegram 内容、抓取规则、岗位数量、岗位排序、数据字段和 HTML 预览保持不变。
- 岗位名称与薪资使用同一粗体普通段落，中间使用全角竖线 `｜`。
- 公司名称使用粗体普通段落。
- 相邻岗位之间使用一条 `---` 分隔线；每个关键词分组的最后一个岗位后不添加分隔线。
- 学历存在时显示，未标明时隐藏整行。
- `detail_url` 继续生成 Markdown 链接，最终以公众号手机预览点击结果验收。
- 文章摘要固定显示“今日新增岗位”和实际新增总数，不使用“样本”描述。
- 搜索关键词显示 `keyword_rows` 中的具体名称，使用 `、` 连接，不显示关键词数量。
- 覆盖城市显示快照头 `cities` 中的具体名称，使用 `、` 连接，不显示城市数量。
- 摘要不显示采集页数；文章结尾固定为 `数据来源，仅供学习研究。`。
- 保留 `article.md`，额外生成 `YYYY-MM-DD 每日新增岗位公告.md` 作为公众号导入文件。
- 动态导入文件不包含一级标题，避免公众号正文重复标题；其余内容与 `article.md` 一致。
- 不开发小程序、自动发布或岗位落地页。
- 未经用户明确授权不得 commit、push、merge 或部署。
- OpenJobFlow 提交标题使用自然中文，不加 `feat:`、`fix:`、`docs:` 前缀，也不加入助手名字。

---

## File Structure

- Modify `src/jobflow/reports/wechat_article.py`：生成公众号文章包；本次调整文章数据、顶部摘要和单岗位 Markdown 结构。
- Modify `src/jobflow/reports/multi_keyword_service.py`：把快照头中的真实城市列表传给公众号文章数据。
- Modify `tests/reports/test_wechat_article.py`：固定公众号兼容的粗体标题、公司和岗位分隔线契约。
- Generate `.pytest_tmp/wechat-markdown-sample/test_article_package_contains_0/wechat/2026-08-26 每日新增岗位公告.md`：通过现有 3 岗位测试夹具生成不进入 Git 的公众号导入小样。
- Keep `docs/development/specs/2026-08-27-wechat-markdown-job-divider-design.md`：记录已确认的设计与人工验收边界。

### Task 1: 固定公众号兼容的 Markdown 岗位格式

**Files:**
- Modify: `tests/reports/test_wechat_article.py`
- Modify: `src/jobflow/reports/wechat_article.py:220-242`

**Interfaces:**
- Consumes: `WechatArticleData.new_job_groups`、`_sorted_postings(postings)`、`_salary_label(posting)`、`_requirement_labels(posting)`。
- Produces: `_build_markdown(data: WechatArticleData) -> str`，其中每个岗位使用粗体标题与公司，相邻岗位间使用 `---`。

- [ ] **Step 1: 写入失败测试，固定公众号导入格式**

在 `tests/reports/test_wechat_article.py` 的 Markdown 测试附近加入：

```python
def test_markdown_uses_official_account_compatible_job_blocks(tmp_path):
    write_wechat_article(sample_data(), PNG, COVER, tmp_path / "wechat")
    markdown = (tmp_path / "wechat" / "article.md").read_text(encoding="utf-8")

    assert "#### AI Agent 工程师" not in markdown
    assert "**AI Agent 工程师｜薪资面议**" in markdown
    assert "**<示例>公司**" in markdown
    assert markdown.count("\n---\n") == 2
    assert "[查看岗位详情 →](https://example.test/jobs/1)" in markdown
```

- [ ] **Step 2: 运行测试并确认旧格式失败**

Run:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
$env:PYTHONIOENCODING = 'utf-8'
python -m pytest tests/reports/test_wechat_article.py::test_markdown_uses_official_account_compatible_job_blocks -q
```

Expected: `FAIL`，失败信息至少包含缺少 `**AI Agent 工程师｜薪资面议**`；旧实现仍输出 `#### AI Agent 工程师　薪资面议`。

- [ ] **Step 3: 最小修改 `_build_markdown`**

把 `src/jobflow/reports/wechat_article.py` 中岗位循环改为以下结构，保留循环外的趋势、分组和免责声明逻辑：

```python
        sorted_postings = _sorted_postings(group.postings)
        for index, posting in enumerate(sorted_postings):
            education_label, skills_label = _requirement_labels(posting)
            lines.extend(
                [
                    f"**{posting.title}｜{_salary_label(posting)}**",
                    "",
                    f"**{posting.company}**",
                    "",
                    f"工作地点：{posting.city}",
                ]
            )
            if education_label is not None:
                lines.extend(["", f"学历要求：{education_label}"])
            lines.extend(["", f"技能要求：{skills_label}"])
            if posting.detail_url:
                lines.extend(["", f"[查看岗位详情 →]({posting.detail_url})"])
            lines.append("")
            if index < len(sorted_postings) - 1:
                lines.extend(["---", ""])
```

- [ ] **Step 4: 运行定向测试并确认通过**

Run:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
$env:PYTHONIOENCODING = 'utf-8'
python -m pytest tests/reports/test_wechat_article.py::test_markdown_uses_official_account_compatible_job_blocks tests/reports/test_wechat_article.py::test_markdown_and_html_render_education_without_repeating_skill_tag tests/reports/test_wechat_article.py::test_markdown_and_html_hide_education_when_source_does_not_provide_it -q
```

Expected: `3 passed`。

- [ ] **Step 5: 检查格式与静态规则**

Run:

```powershell
python -m ruff check src/jobflow/reports/wechat_article.py tests/reports/test_wechat_article.py
python -m ruff format --check src/jobflow/reports/wechat_article.py tests/reports/test_wechat_article.py
```

Expected: 两条命令均以退出码 `0` 结束；第一条显示 `All checks passed!`。

### Task 2: 生成并验证 3 岗位公众号导入小样

**Files:**
- Generate: `.pytest_tmp/wechat-markdown-sample/test_article_package_contains_0/wechat/2026-08-26 每日新增岗位公告.md`

**Interfaces:**
- Consumes: `sample_data()`，其中 `AI Agent` 分组固定包含 3 个岗位。
- Produces: 一个不进入 Git、可直接导入微信公众号后台的动态中文文件名小样。

- [ ] **Step 1: 使用现有确定性夹具生成文章包**

Run:

```powershell
New-Item -ItemType Directory -Path .pytest_tmp -Force | Out-Null
$env:PYTHONPATH = (Resolve-Path src).Path
$env:PYTHONIOENCODING = 'utf-8'
python -m pytest tests/reports/test_wechat_article.py::test_article_package_contains_machine_and_official_account_markdown -q --basetemp=.pytest_tmp/wechat-markdown-sample
```

Expected: `1 passed`，并在 `.pytest_tmp/wechat-markdown-sample/` 下生成包含 3 个岗位的 `wechat/2026-08-26 每日新增岗位公告.md`。

- [ ] **Step 2: 解析实际小样路径并检查内容**

Run:

```powershell
$sample = Get-Item -LiteralPath '.pytest_tmp/wechat-markdown-sample/test_article_package_contains_0/wechat/2026-08-26 每日新增岗位公告.md'
$sample.FullName
Get-Content -LiteralPath $sample.FullName -Encoding UTF8
```

Expected: 输出动态中文文件名的绝对路径；正文直接从摘要开始，包含 3 个粗体岗位标题、3 个粗体公司名称、2 条独立的 `---` 分隔线，并且没有一级标题或以 `####` 开头的岗位标题。

- [ ] **Step 3: 在微信公众号后台进行真实导入验收**

人工操作：

1. 新建或复制一份公众号草稿，保留当前完整草稿不删除。
2. 导入 Step 2 输出的动态中文文件名 Markdown。
3. 确认 3 个岗位均显示岗位名称、`薪资面议`、公司、地点、技能和详情链接。
4. 确认相邻岗位之间各有一条细线，最后一个岗位后没有细线。
5. 发送手机预览并逐一点击 3 个“查看岗位详情 →”。

Expected: 3 个岗位字段完整、2 条分隔线清楚、3 条链接均能打开对应地址。任何一项失败都停在小样阶段，不生成完整文章。

### Task 3: 小样通过后的回归检查与完整文章交接

**Files:**
- Verify: `src/jobflow/reports/wechat_article.py`
- Verify: `tests/reports/test_wechat_article.py`
- Keep untracked until authorization: implementation and design/plan documentation changes。

**Interfaces:**
- Consumes: Task 2 的公众号编辑器和手机预览通过结果。
- Produces: 可由 Ubuntu 现有 V1.3.3 文章生成接口重新生成完整岗位公告的代码状态。

- [ ] **Step 1: 运行微信文章模块完整回归**

Run:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
$env:PYTHONIOENCODING = 'utf-8'
python -m pytest tests/reports/test_wechat_article.py -q
```

Expected: 文件内全部测试通过，无失败或错误。

- [ ] **Step 2: 运行项目完整测试与 Ruff 检查**

Run:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
$env:PYTHONIOENCODING = 'utf-8'
python -m pytest -q
python -m ruff check .
python -m ruff format --check src/jobflow/reports/wechat_article.py tests/reports/test_wechat_article.py
```

Expected: pytest 全部通过；Ruff 检查与本次涉及文件的格式检查均以退出码 `0` 结束。

- [ ] **Step 3: 审查差异和 Git 边界**

Run:

```powershell
git diff --check
git status --short --branch
git diff -- src/jobflow/reports/wechat_article.py tests/reports/test_wechat_article.py docs/development/specs/2026-08-27-wechat-markdown-job-divider-design.md docs/development/plans/2026-08-27-wechat-markdown-job-divider.md
```

Expected: 没有空白错误；差异只涉及本计划列出的代码、测试和文档；`.pytest_tmp/` 不出现在 Git 状态中。

- [ ] **Step 4: 等待用户授权 Git 操作**

报告测试结果、当前分支和待提交文件。只有用户给出明确提交并推送授权后，才执行 `git add`、`git commit` 和 `git push`；提交标题由用户确认，且不添加类型前缀或助手署名。
