# 微信文章包宿主机读取权限修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Ubuntu 宿主机普通用户无需 `sudo` 即可读取微信文章包，同时保留容器用户写入和现有原子替换行为。

**Architecture:** 在临时文章包完成写入后，对四个文件显式执行 `chmod(0o644)`，对临时目录执行 `chmod(0o755)`，再沿用现有 `os.replace()` 原子替换。用平台无关的调用记录测试验证代码主动设置权限，并用 POSIX 条件测试和 Docker 探针验证最终权限位。

**Tech Stack:** Python 3.12、pathlib、pytest、Docker Compose、Markdown

## Global Constraints

- 最终 `wechat` 目录权限固定为 `0755`。
- `article.md`、`article.html`、`trend.png`、`manifest.json` 权限固定为 `0644`。
- 不修改微信模板内容、发送接口、投递状态机、数据库或文章包目录结构。
- 保留原子替换、旧包恢复和异常清理逻辑。
- Windows 不断言最终 POSIX 权限位；Linux/Docker 必须验证精确的 `0755/0644`。
- 不修改历史文章包；新权限在重新生成文章包后生效。
- Git 提交信息使用自然中文，不使用 `docs:`、`fix:`、`feat:` 等前缀；每次提交仍需用户明确授权。

---

## 文件结构

- `src/jobflow/reports/wechat_article.py`：在文章包原子替换前显式设置最终权限。
- `tests/reports/test_wechat_article.py`：验证显式 `chmod` 调用、POSIX 最终权限和覆盖生成后的权限。
- `docs/wechat-test-account.md`：修正 `runtime` 权限命令，并记录普通用户直接读取文章包的验收标准。

### Task 1: 显式设置并验证文章包权限

**Files:**
- Modify: `src/jobflow/reports/wechat_article.py:176-200`
- Test: `tests/reports/test_wechat_article.py:1-88`

**Interfaces:**
- Consumes: `write_wechat_article(data: WechatArticleData, trend_png: bytes, output_dir: Path) -> ArticleManifest`
- Produces: 保持相同函数签名和返回值；新增行为是最终目录 `0755`、清单内四个文件 `0644`。

- [ ] **Step 1: 写入平台无关的失败测试**

在 `tests/reports/test_wechat_article.py` 顶部增加：

```python
from datetime import date
import json
import os
from pathlib import Path
import stat
```

在文件末尾增加：

```python
def test_article_package_sets_explicit_permissions(tmp_path, monkeypatch):
    chmod_calls: list[tuple[str, int]] = []
    original_chmod = Path.chmod

    def record_chmod(path: Path, mode: int) -> None:
        chmod_calls.append((path.name, mode))
        original_chmod(path, mode)

    monkeypatch.setattr(Path, "chmod", record_chmod)

    output = tmp_path / "wechat"
    manifest = write_wechat_article(sample_data(), PNG, output)

    file_modes = {
        name: mode for name, mode in chmod_calls if name in manifest.files
    }
    assert file_modes == {name: 0o644 for name in manifest.files}
    assert sum(
        name.startswith("wechat-article-") and mode == 0o755
        for name, mode in chmod_calls
    ) == 1


@pytest.mark.skipif(os.name == "nt", reason="需要 POSIX 权限位语义")
def test_article_package_permissions_survive_atomic_replacement(tmp_path):
    output = tmp_path / "wechat"

    for _ in range(2):
        manifest = write_wechat_article(sample_data(), PNG, output)

        assert stat.S_IMODE(output.stat().st_mode) == 0o755
        for filename in manifest.files:
            assert stat.S_IMODE((output / filename).stat().st_mode) == 0o644
```

- [ ] **Step 2: 在 Windows 运行定向测试并确认新测试失败**

Run:

```powershell
python -m pytest tests/reports/test_wechat_article.py::test_article_package_sets_explicit_permissions -v
```

Expected: `FAIL`，`file_modes` 为空且没有 `0755` 目录调用。

- [ ] **Step 3: 用当前 Linux 镜像确认实际目录仍为 0700**

Run:

```bash
docker compose build api
docker compose run --rm --no-deps --entrypoint python api - <<'PY'
from datetime import date
from pathlib import Path
import stat
import tempfile

from jobflow.reports.wechat_article import WechatArticleData, write_wechat_article

data = WechatArticleData(
    report_date=date(2026, 8, 26),
    city_count=4,
    pages_per_city=3,
    keyword_rows=(("AI Agent", 18, 3),),
    city_advantages=(("上海", "AI Agent", 5),),
    weekly_summary=None,
)

with tempfile.TemporaryDirectory() as root:
    output = Path(root) / "wechat"
    manifest = write_wechat_article(data, b"\x89PNG\r\n\x1a\narticle", output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o755
    for filename in manifest.files:
        assert stat.S_IMODE((output / filename).stat().st_mode) == 0o644

print("POSIX_PERMISSIONS_OK")
PY
```

Expected: `AssertionError`，因为现有 `tempfile.mkdtemp()` 目录权限为 `0700`。

- [ ] **Step 4: 写入最小权限实现**

在 `manifest.json` 写完之后、`if output_dir.exists():` 之前增加：

```python
        for filename in manifest.files:
            (temp_dir / filename).chmod(0o644)
        temp_dir.chmod(0o755)
```

不要移动或重写现有备份、`os.replace()`、恢复和 `finally` 清理代码。

- [ ] **Step 5: 运行文章包测试**

Run:

```powershell
python -m pytest tests/reports/test_wechat_article.py -v
```

Expected on Windows: `6 passed, 1 skipped`；跳过项是 POSIX 最终权限测试。

- [ ] **Step 6: 运行 Ruff**

Run:

```powershell
python -m ruff check src/jobflow/reports/wechat_article.py tests/reports/test_wechat_article.py
```

Expected: `All checks passed!`

- [ ] **Step 7: 重建 Linux 镜像并复跑权限探针**

重新执行 Step 3 的 Docker 命令。

Expected: 输出 `POSIX_PERMISSIONS_OK`，没有 `AssertionError`。

- [ ] **Step 8: 检查改动并等待提交授权**

Run:

```powershell
git diff --check
git diff -- src/jobflow/reports/wechat_article.py tests/reports/test_wechat_article.py
git status --short --branch
```

Expected: 只有实现文件、测试文件和尚未提交的实施计划文件发生预期变化。获得用户明确授权后再提交，建议提交信息：

```text
修复微信文章包读取权限
```

### Task 2: 更新 Ubuntu 验收说明并完成回归

**Files:**
- Modify: `docs/wechat-test-account.md:49-67,94-100`

**Interfaces:**
- Consumes: Task 1 生成的 `0755` 目录和 `0644` 文件。
- Produces: Ubuntu 操作者可直接执行的部署与文章包读取说明。

- [ ] **Step 1: 修正 runtime 权限命令**

将：

```bash
chmod 755 runtime
```

改为：

```bash
sudo chmod 755 runtime
```

原因是前一条 `sudo chown "$APP_UID:$APP_GID" runtime` 已将目录所有权切换给容器用户，宿主机普通用户不能再直接执行 `chmod`。

- [ ] **Step 2: 补充文章包权限验收**

在四个文件的预期列表后增加：

```markdown
新生成的 `wechat` 目录权限应为 `0755`，四个文件权限应为 `0644`。宿主机普通用户应能直接执行上述 `find` 命令，不需要 `sudo`；历史文章包需要重新生成后才会获得新权限。
```

- [ ] **Step 3: 运行完整非 PostgreSQL 回归**

Run:

```powershell
python -m pytest -q --ignore=tests/integration
```

Expected: 在原有 `305 passed` 基线上新增一个跨平台权限测试通过和一个 Windows POSIX 测试跳过，即 `306 passed, 1 skipped`；若现有测试分类不同，以零失败为硬性标准并记录实际计数。

- [ ] **Step 4: 运行完整 Ruff 和 Compose 解析**

Run:

```powershell
python -m ruff check .
docker compose config --quiet
```

Expected: Ruff 输出 `All checks passed!`，Compose 命令退出码为 `0`。

- [ ] **Step 5: 最终自审并等待提交授权**

Run:

```powershell
git diff --check
git diff --stat
git status --short --branch
```

核对：

- 无 Token、appsecret、OpenID 或个人服务器地址；
- 没有数据库、接口、模板或状态机改动；
- 设计文档提交 `03f411f` 保持独立；
- 代码和文档未经授权不提交、不推送。

获得用户明确授权后再提交，建议提交信息：

```text
更新微信文章包权限说明
```

## Ubuntu 最终验收

代码提交并推送、服务器拉取和重建后，由服务器维护者执行：

```bash
REPORT_DATE="$(date +%F)"
find "runtime/reports/${REPORT_DATE}/wechat" -maxdepth 1 -type f -printf '%m %f\n' | sort
```

Expected:

```text
644 article.html
644 article.md
644 manifest.json
644 trend.png
```

并执行：

```bash
stat -c '%a %n' "runtime/reports/${REPORT_DATE}/wechat"
```

Expected: 输出以 `755` 开头。该验收应在下一次正常每日任务生成新文章包后执行；不得为权限测试重复发送同日微信模板消息。
