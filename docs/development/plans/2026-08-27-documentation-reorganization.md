# OpenJobFlow Documentation Reorganization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Reorganize `docs/` by reader purpose, preserve the current handoff edits, repair every affected repository link, and leave the public documentation tests passing.

**Architecture:** Keep `docs/README.md` and `docs/project-handoff.md` as stable entrypoints. Move current guides, references, development material, operations evidence, and historical plans into distinct directories; use automated path-contract and Markdown-link tests to prevent silent breakage.

**Tech Stack:** Markdown, Git, PowerShell, Python `pathlib`, pytest.

## Global Constraints

- Do not delete any existing Markdown document or image asset.
- Preserve the current uncommitted V1.3.2 content in `docs/project-handoff.md`.
- Keep only the WeChat V1.3.2 and documentation-reorganization specs/plans in `docs/development/`; archive older specs/plans without rewriting their historical content.
- Do not retain redirect stubs at old paths.
- Do not add real `.env` values, passwords, API keys, Webhooks, Tokens, Cookies, private keys, personal server addresses, subscription URLs, or personal absolute paths.
- OpenJobFlow commit titles use natural Chinese without `docs:`、`fix:`、`feat:` prefixes.
- Do not commit or push until the user gives separate explicit authorization.
- Do not use `git reset --hard`, `git add .`, or broad restore commands.

---

## File Structure

### Stable entrypoints

- Keep: `docs/README.md` — navigation by reader goal.
- Keep: `docs/project-handoff.md` — current development and deployment handoff.

### Public guides

- Move: `docs/guides/ubuntu-deployment.md` → `docs/guides/ubuntu-deployment.md`.
- Move: `docs/guides/wechat-test-account.md` → `docs/guides/wechat-test-account.md`.

### Reference material

- Move: `docs/reference/architecture.md` → `docs/reference/architecture.md`.
- Move: `docs/reference/data-sources.md` → `docs/reference/data-sources.md`.
- Move: `docs/reference/platform-evolution-design.md` → `docs/reference/platform-evolution-design.md`.

### Current development material

- Create: `docs/development/README.md` — current development reading order and evidence boundary.
- Move: `docs/development/learning-notes.md` → `docs/development/learning-notes.md`.
- Move current specs to `docs/development/specs/`:
  - `2026-08-26-wechat-official-daily-delivery-design.md`
  - `2026-08-27-wechat-article-package-permissions-design.md`
  - `2026-08-27-documentation-reorganization-design.md`
- Move current plans to `docs/development/plans/`:
  - `2026-08-26-wechat-official-daily-delivery.md`
  - `2026-08-27-wechat-article-package-permissions.md`
  - `2026-08-27-documentation-reorganization.md`

### Historical material

- Create: `docs/archive/README.md` — historical-use warning and archive index.
- Preserve the existing files in `docs/archive/specs/` and `docs/archive/plans/`.
- Move every other file from `docs/superpowers/specs/` to `docs/archive/specs/`.
- Move every other file from `docs/superpowers/plans/` to `docs/archive/plans/`.
- Remove the empty `docs/superpowers/specs/`, `docs/superpowers/plans/`, and `docs/superpowers/` directories after verifying they contain no files.

### Tests and public entrypoints

- Modify: `tests/docs/test_public_assets.py` — new layout contract and repository-wide local Markdown link test.
- Modify: `README.md` — new guide/reference paths.
- Modify: `README.zh-CN.md` — same new paths as the English README.
- Modify every Markdown file whose navigational links still use an old path.

---

### Task 1: Protect Existing Work and Add the Documentation Layout Contract

**Files:**
- Modify: `tests/docs/test_public_assets.py:10-17`
- Modify: `tests/docs/test_public_assets.py:215-220`
- Read only: `docs/project-handoff.md`

**Interfaces:**
- Consumes: current Git worktree and approved directory design.
- Produces: a failing pytest contract describing the exact target documentation layout.

- [x] **Step 1: Capture the current branch, handoff diff, and document inventory**

Run from the repository root:

```powershell
git status --short --branch
git diff -- docs/project-handoff.md
Get-ChildItem docs -Recurse -File | ForEach-Object { $_.FullName.Substring((Resolve-Path .).Path.Length + 1) } | Sort-Object
```

Expected:

```text
branch = bugfix/wechat-article-permissions
docs/project-handoff.md is modified
the documentation-reorganization design is untracked
20 files exist under docs/superpowers/specs
18 files exist under docs/superpowers/plans after this implementation plan is saved
```

Save the `docs/project-handoff.md` diff in the terminal record. Do not restore or stage it.

- [x] **Step 2: Define reusable docs paths in the public-assets test**

Add below `DOCS_INDEX`:

```python
DOCS_ROOT = ROOT / "docs"
GUIDES_ROOT = DOCS_ROOT / "guides"
REFERENCE_ROOT = DOCS_ROOT / "reference"
DEVELOPMENT_ROOT = DOCS_ROOT / "development"
ARCHIVE_ROOT = DOCS_ROOT / "archive"
```

Keep `DEMO_IMAGE` unchanged.

- [x] **Step 3: Add the exact directory-layout test**

Add after `test_docs_index_points_to_bilingual_public_entrypoints`:

```python
def test_documentation_is_grouped_by_reader_goal() -> None:
    required_files = {
        DOCS_INDEX,
        DOCS_ROOT / "project-handoff.md",
        GUIDES_ROOT / "ubuntu-deployment.md",
        GUIDES_ROOT / "wechat-test-account.md",
        REFERENCE_ROOT / "architecture.md",
        REFERENCE_ROOT / "data-sources.md",
        REFERENCE_ROOT / "platform-evolution-design.md",
        DEVELOPMENT_ROOT / "README.md",
        DEVELOPMENT_ROOT / "learning-notes.md",
        DEVELOPMENT_ROOT / "specs" / "2026-08-26-wechat-official-daily-delivery-design.md",
        DEVELOPMENT_ROOT / "specs" / "2026-08-27-wechat-article-package-permissions-design.md",
        DEVELOPMENT_ROOT / "specs" / "2026-08-27-documentation-reorganization-design.md",
        DEVELOPMENT_ROOT / "plans" / "2026-08-26-wechat-official-daily-delivery.md",
        DEVELOPMENT_ROOT / "plans" / "2026-08-27-wechat-article-package-permissions.md",
        DEVELOPMENT_ROOT / "plans" / "2026-08-27-documentation-reorganization.md",
        ARCHIVE_ROOT / "README.md",
    }
    legacy_files = {
        DOCS_ROOT / "ubuntu-deployment.md",
        DOCS_ROOT / "wechat-test-account.md",
        DOCS_ROOT / "architecture.md",
        DOCS_ROOT / "data-sources.md",
        DOCS_ROOT / "platform-evolution-design.md",
        DOCS_ROOT / "learning-notes.md",
    }

    assert all(path.is_file() for path in required_files)
    assert not any(path.exists() for path in legacy_files)
    assert not (DOCS_ROOT / "superpowers").exists()
```

- [x] **Step 4: Run the layout test and verify it fails for the intended reason**

Run:

```powershell
pytest -q tests/docs/test_public_assets.py::test_documentation_is_grouped_by_reader_goal
```

Expected: `FAIL` because `docs/guides/`, `docs/reference/`, and `docs/development/` do not exist yet. A syntax/import failure is not an acceptable expected failure.

- [x] **Step 5: Review the Task 1 diff without staging it**

```powershell
git diff -- tests/docs/test_public_assets.py
git status --short
```

Expected: only the existing handoff modification, the untracked design, and the intended test edit are visible.

---

### Task 2: Move Documents and Build the New Navigation Indexes

**Files:**
- Move: all paths listed in the File Structure section.
- Create: `docs/development/README.md`
- Create: `docs/archive/README.md`
- Modify: `docs/README.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Test: `tests/docs/test_public_assets.py`

**Interfaces:**
- Consumes: layout contract from Task 1 and the current docs inventory.
- Produces: the approved physical directory structure and working public entrypoint links.

- [x] **Step 1: Create destination directories and verify their resolved paths**

```powershell
$repoRoot = (Resolve-Path .).Path
$destinations = @(
  'docs\guides',
  'docs\reference',
  'docs\development\specs',
  'docs\development\plans',
  'docs\archive\specs',
  'docs\archive\plans'
)
foreach ($relative in $destinations) {
  $path = Join-Path $repoRoot $relative
  New-Item -ItemType Directory -Path $path -Force | Out-Null
  if (-not $path.StartsWith((Join-Path $repoRoot 'docs'), [StringComparison]::OrdinalIgnoreCase)) {
    throw "Destination escaped docs: $path"
  }
}
```

Expected: all resolved destinations remain under `<repository>/docs`.

- [x] **Step 2: Move the six top-level documents with Git history preserved**

```powershell
git mv -- docs/guides/ubuntu-deployment.md docs/guides/ubuntu-deployment.md
git mv -- docs/guides/wechat-test-account.md docs/guides/wechat-test-account.md
git mv -- docs/reference/architecture.md docs/reference/architecture.md
git mv -- docs/reference/data-sources.md docs/reference/data-sources.md
git mv -- docs/reference/platform-evolution-design.md docs/reference/platform-evolution-design.md
git mv -- docs/development/learning-notes.md docs/development/learning-notes.md
```

Expected: Git reports renames rather than delete-and-untracked pairs after related content settles.

- [x] **Step 3: Move the exact active specs and plans**

```powershell
git mv -- docs/development/specs/2026-08-26-wechat-official-daily-delivery-design.md docs/development/specs/
git mv -- docs/development/specs/2026-08-27-wechat-article-package-permissions-design.md docs/development/specs/
git mv -- docs/development/specs/2026-08-27-documentation-reorganization-design.md docs/development/specs/
git mv -- docs/development/plans/2026-08-26-wechat-official-daily-delivery.md docs/development/plans/
git mv -- docs/development/plans/2026-08-27-wechat-article-package-permissions.md docs/development/plans/
git mv -- docs/development/plans/2026-08-27-documentation-reorganization.md docs/development/plans/
```

Expected: `docs/development/specs/` contains exactly three files and `docs/development/plans/` contains exactly three files.

- [x] **Step 4: Move the remaining superpowers documents into archive**

```powershell
$specSource = (Resolve-Path 'docs\superpowers\specs').Path
$planSource = (Resolve-Path 'docs\superpowers\plans').Path
$specTarget = (Resolve-Path 'docs\archive\specs').Path
$planTarget = (Resolve-Path 'docs\archive\plans').Path

Get-ChildItem -LiteralPath $specSource -File -Filter '*.md' | ForEach-Object {
  git mv -- $_.FullName (Join-Path $specTarget $_.Name)
}
Get-ChildItem -LiteralPath $planSource -File -Filter '*.md' | ForEach-Object {
  git mv -- $_.FullName (Join-Path $planTarget $_.Name)
}
```

Expected final counts:

```text
docs/development/specs = 3
docs/development/plans = 3
docs/archive/specs = 20
docs/archive/plans = 20
```

The archive counts include the three pre-existing archived specs, five pre-existing archived plans, and the newly archived completed files.

- [x] **Step 5: Verify `docs/superpowers/` is empty before removing directories**

```powershell
$remaining = @(Get-ChildItem -LiteralPath docs\superpowers -Recurse -File)
if ($remaining.Count -ne 0) {
  $remaining.FullName
  throw 'docs/superpowers still contains files'
}
Remove-Item -LiteralPath docs\superpowers\specs
Remove-Item -LiteralPath docs\superpowers\plans
Remove-Item -LiteralPath docs\superpowers
```

Expected: only the three verified empty directories are removed; no recursive delete is used.

- [x] **Step 6: Create the current-development index**

Create `docs/development/README.md` with these sections and links:

```markdown
# 当前开发资料

本目录只保留当前版本仍在开发或等待验收的设计与计划。代码、测试、项目交接和服务器实际输出是完成状态的最终依据。

## 阅读顺序

1. [`../project-handoff.md`](../project-handoff.md)：当前 Git、部署和下一步。
2. [`specs/2026-08-26-wechat-official-daily-delivery-design.md`](specs/2026-08-26-wechat-official-daily-delivery-design.md)：V1.3.2 微信推送设计。
3. [`plans/2026-08-26-wechat-official-daily-delivery.md`](plans/2026-08-26-wechat-official-daily-delivery.md)：V1.3.2 实施计划。
4. [`specs/2026-08-27-wechat-article-package-permissions-design.md`](specs/2026-08-27-wechat-article-package-permissions-design.md)：文章包权限修复设计。
5. [`plans/2026-08-27-wechat-article-package-permissions.md`](plans/2026-08-27-wechat-article-package-permissions.md)：文章包权限修复计划。
6. [`specs/2026-08-27-documentation-reorganization-design.md`](specs/2026-08-27-documentation-reorganization-design.md)：文档目录整理设计。
7. [`plans/2026-08-27-documentation-reorganization.md`](plans/2026-08-27-documentation-reorganization.md)：文档目录整理计划。

## 状态边界

- 微信测试号手动送达已经验收；
- 文章包权限修复已在功能分支完成，尚未合并部署；
- 微信第一次正式 systemd 定时送达仍待验收；
- 计划中的步骤不自动代表已经实现。

历史设计与计划见 [`../archive/README.md`](../archive/README.md)。
```

- [x] **Step 7: Create the archive boundary index**

Create `docs/archive/README.md`:

```markdown
# 历史设计与实施计划

本目录保存已经完成、被替代或不再作为当前入口的设计与实施计划，用于追溯项目决策。

## 使用边界

- `specs/` 保存历史需求和设计；
- `plans/` 保存历史任务拆分和执行顺序；
- 历史文档中的计划、路径和命令不代表当前实现；
- 当前状态先看 [`../project-handoff.md`](../project-handoff.md)；
- 当前部署教程见 [`../guides/ubuntu-deployment.md`](../guides/ubuntu-deployment.md)；
- 当前架构见 [`../reference/architecture.md`](../reference/architecture.md)。

不要根据归档计划直接操作服务器。继续开发前应重新检查代码、测试、Git 和服务器实际输出。
```

- [x] **Step 8: Rewrite `docs/README.md` as the reader-goal index**

Keep its safety and evidence language, but replace the flat current-document list with these exact destinations:

```text
Public entrypoints: ../README.md, ../README.zh-CN.md, assets/jobflow-demo.png
First run: guides/ubuntu-deployment.md, guides/wechat-test-account.md
Understand the system: reference/architecture.md, reference/data-sources.md, reference/platform-evolution-design.md
Resume development: project-handoff.md
Current work: development/README.md, development/learning-notes.md
Operational evidence: operations/2026-08-25-daily-update-production-acceptance.md
History: archive/README.md
```

Do not list every archived spec in the top-level index.

- [x] **Step 9: Update the bilingual public README guide links and structure snippets**

Apply this path mapping in both root READMEs:

```text
docs/guides/ubuntu-deployment.md    → docs/guides/ubuntu-deployment.md
docs/guides/wechat-test-account.md  → docs/guides/wechat-test-account.md
docs/reference/architecture.md         → docs/reference/architecture.md
docs/reference/data-sources.md         → docs/reference/data-sources.md
```

Update any displayed project tree so it shows `docs/guides/`, `docs/reference/`, `docs/development/`, `docs/operations/`, and `docs/archive/` without listing personal paths.

- [x] **Step 10: Update the bilingual README contract expectation**

In `test_bilingual_readmes_keep_critical_commands_and_links_in_sync`, replace:

```python
"docs/guides/ubuntu-deployment.md",
```

with:

```python
"docs/guides/ubuntu-deployment.md",
```

Add `docs/guides/wechat-test-account.md` to the English and Chinese onboarding requirements only if both README files continue to expose that guide after the rewrite.

- [x] **Step 11: Run the structure and public-entrypoint tests**

```powershell
pytest -q tests/docs/test_public_assets.py -k "documentation_is_grouped or english_readme or chinese_readme or bilingual_readmes or docs_index"
```

Expected: all selected tests pass. Local links inside moved development/archive documents are handled in Task 3.

---

### Task 3: Repair Every Local Markdown Link and Add Regression Coverage

**Files:**
- Modify: `tests/docs/test_public_assets.py:1-5`
- Modify: `tests/docs/test_public_assets.py` after the existing bilingual README link test.
- Modify: every Markdown file reported by the new link test.

**Interfaces:**
- Consumes: final directory layout from Task 2.
- Produces: a repository-wide test proving every local Markdown link and image target resolves.

- [x] **Step 1: Import URL decoding for Markdown targets**

Replace:

```python
from urllib.parse import urlparse
```

with:

```python
from urllib.parse import unquote, urlparse
```

- [x] **Step 2: Add a helper that ignores fenced examples**

Add below `_tracked_public_text_files`:

```python
def _markdown_without_fenced_code(text: str) -> str:
    visible_lines: list[str] = []
    inside_fence = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            inside_fence = not inside_fence
            continue
        if not inside_fence:
            visible_lines.append(line)
    return "\n".join(visible_lines)
```

- [x] **Step 3: Add the repository-wide local Markdown link test**

Add after `test_bilingual_readme_local_links_resolve`:

```python
def test_all_local_markdown_links_resolve() -> None:
    markdown_files = sorted(
        path
        for path in ROOT.rglob("*.md")
        if ".git" not in path.parts and ".pytest_cache" not in path.parts
    )
    broken: list[str] = []

    for markdown_path in markdown_files:
        text = _markdown_without_fenced_code(markdown_path.read_text(encoding="utf-8"))
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative_target = unquote(target.split("#", 1)[0])
            if not relative_target:
                continue
            resolved = markdown_path.parent / relative_target
            if not resolved.exists():
                source = markdown_path.relative_to(ROOT).as_posix()
                broken.append(f"{source} -> {target}")

    assert not broken, "broken local Markdown links:\n" + "\n".join(broken)
```

- [x] **Step 4: Run the new test and capture every broken link**

```powershell
pytest -q tests/docs/test_public_assets.py::test_all_local_markdown_links_resolve
```

Expected: `FAIL` listing old relative links after the moves. Fix the complete reported list before rerunning.

- [x] **Step 5: Apply the repository path mapping**

Use these mappings for repository-root paths:

```text
docs/guides/ubuntu-deployment.md                → docs/guides/ubuntu-deployment.md
docs/guides/wechat-test-account.md              → docs/guides/wechat-test-account.md
docs/reference/architecture.md                     → docs/reference/architecture.md
docs/reference/data-sources.md                     → docs/reference/data-sources.md
docs/reference/platform-evolution-design.md        → docs/reference/platform-evolution-design.md
docs/development/learning-notes.md                   → docs/development/learning-notes.md
docs/superpowers/specs/<active file>     → docs/development/specs/<same file>
docs/superpowers/plans/<active file>     → docs/development/plans/<same file>
docs/superpowers/specs/<completed file>  → docs/archive/specs/<same file>
docs/superpowers/plans/<completed file>  → docs/archive/plans/<same file>
```

For relative links inside moved files, calculate the target from the file's new parent. Examples:

```text
from docs/development/README.md to handoff       → ../project-handoff.md
from docs/archive/README.md to Ubuntu guide      → ../guides/ubuntu-deployment.md
from docs/development/specs/<file> to handoff    → ../../project-handoff.md
from docs/archive/specs/<file> to a root README  → ../../../README.md
```

Do not replace historical plain text merely because it contains an old path. Change navigational Markdown links and currently executable instructions; leave historical narrative intact unless it points readers to a nonexistent file.

- [x] **Step 6: Update current handoff links without overwriting its existing content**

Before editing:

```powershell
git diff -- docs/project-handoff.md
```

Only replace affected paths using the same mapping. After editing, verify that the following V1.3.2 facts still appear:

```text
bugfix/wechat-article-permissions
03f411f
f7522f0
41bd25a
306 passed, 1 skipped
```

Run:

```powershell
Select-String -Path docs/project-handoff.md -Pattern 'bugfix/wechat-article-permissions|03f411f|f7522f0|41bd25a|306 passed, 1 skipped'
```

Expected: all five patterns are found.

- [x] **Step 7: Rerun the local-link test**

```powershell
pytest -q tests/docs/test_public_assets.py::test_all_local_markdown_links_resolve
```

Expected: `PASS` with no missing documents or images.

- [x] **Step 8: Scan for navigational old-path residue**

```powershell
$patterns = @(
  '](docs/guides/ubuntu-deployment.md',
  '](docs/guides/wechat-test-account.md',
  '](docs/reference/architecture.md',
  '](docs/reference/data-sources.md',
  '](docs/reference/platform-evolution-design.md',
  '](docs/development/learning-notes.md',
  '](docs/superpowers/'
)
Get-ChildItem -Recurse -File -Include '*.md' |
  Select-String -SimpleMatch -Pattern $patterns
```

Expected: no output. Plain historical code/path text is reviewed separately and is not automatically rewritten.

- [x] **Step 9: Include untracked documentation in the sensitive-information scan**

Replace `_tracked_public_text_files` with the following implementation and rename it to `_public_text_files_for_scan`:

```python
def _public_text_files_for_scan() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    tracked_paths = {
        ROOT / item
        for item in result.stdout.split("\0")
        if item
        and (
            (ROOT / item).name in PUBLIC_TEXT_FILENAMES
            or (ROOT / item).suffix.lower() in PUBLIC_TEXT_SUFFIXES
        )
    }
    documentation_paths = set(DOCS_ROOT.rglob("*.md"))
    return sorted(tracked_paths | documentation_paths)
```

Update `test_tracked_public_text_does_not_expose_personal_environment` to iterate over `_public_text_files_for_scan()`. This keeps the existing tracked-file coverage and adds the new untracked indexes and plan before staging.

- [x] **Step 10: Rerun link and sensitive-information tests**

```powershell
pytest -q tests/docs/test_public_assets.py -k "all_local_markdown_links or personal_environment"
```

Expected: both tests pass.

---

### Task 4: Final Safety, Diff, and Test Gate

**Files:**
- Verify: all moved and modified documentation files.
- Verify: `tests/docs/test_public_assets.py`.
- Do not modify: business code, migrations, Compose configuration, or runtime files.

**Interfaces:**
- Consumes: completed structure and repaired links from Tasks 2-3.
- Produces: a reviewed, uncommitted documentation reorganization ready for explicit commit authorization.

- [x] **Step 1: Verify document counts and exact current/archive sets**

```powershell
[pscustomobject]@{
  DevelopmentSpecs = (Get-ChildItem docs\development\specs -File -Filter '*.md').Count
  DevelopmentPlans = (Get-ChildItem docs\development\plans -File -Filter '*.md').Count
  ArchiveSpecs = (Get-ChildItem docs\archive\specs -File -Filter '*.md').Count
  ArchivePlans = (Get-ChildItem docs\archive\plans -File -Filter '*.md').Count
  AllDocsMarkdown = (Get-ChildItem docs -Recurse -File -Filter '*.md').Count
} | Format-List
```

Expected:

```text
DevelopmentSpecs = 3
DevelopmentPlans = 3
ArchiveSpecs = 20
ArchivePlans = 20
AllDocsMarkdown = 57
```

The total includes `docs/README.md`, handoff, guides, references, development/archive indexes, learning notes, one operations record, 23 specs, and 23 plans.

- [x] **Step 2: Run formatting and public-document safety tests**

```powershell
git diff --check
pytest -q tests/docs/test_public_assets.py
```

Expected: `git diff --check` produces no output and the public-assets test file passes completely.

- [x] **Step 3: Run the non-PostgreSQL regression suite because a shared test module changed**

```powershell
pytest -q --ignore=tests/integration --ignore=tests/postgres
```

Expected baseline: at least the previously observed `306 passed, 1 skipped`, adjusted upward by the two new documentation tests; no failures are allowed.

- [x] **Step 4: Run Ruff on the modified Python test**

```powershell
ruff check tests/docs/test_public_assets.py
ruff format --check tests/docs/test_public_assets.py
```

Expected: both commands exit `0`.

- [x] **Step 5: Review the complete change boundary**

```powershell
git status --short
git diff --stat
git diff --summary
git diff -- docs/project-handoff.md
git diff -- tests/docs/test_public_assets.py
```

Expected:

- documentation moves, two new indexes, and the two approved design/plan files;
- README and Markdown link changes;
- the documentation test changes;
- no `.env`, runtime output, image replacement, business code, migration, or unrelated source change.

- [x] **Step 6: Stop at the commit authorization gate**

Report the final tests, branch, moved-file counts, changed-file list, and any warnings. Do not stage, commit, push, or create a PR.

After the user explicitly authorizes the documentation commit, use exact-file staging and a natural Chinese title:

```powershell
git add -- README.md README.zh-CN.md docs tests/docs/test_public_assets.py
git diff --cached --check
git diff --cached --name-status
git commit -m "整理 OpenJobFlow 文档目录"
```

Do not push this commit until the user separately authorizes the branch push or confirms it should be included in the existing Pull Request.
