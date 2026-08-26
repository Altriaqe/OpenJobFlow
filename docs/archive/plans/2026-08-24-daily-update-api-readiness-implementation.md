# JobFlow 每日任务等待 API 就绪实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** 让每日任务在检查快照前最多等待 API 就绪 5 分钟，消除服务器开机补跑时的 API 启动竞态。

**Architecture:** 在 \`ops/daily_update.sh\` 内增加一个独立的 \`wait_for_api_ready\` shell 函数。函数同时受 300 秒截止时间和 60 次尝试上限约束，每次请求最多 3 秒、失败后最多等待 5 秒；成功后进入原有流程，超时则在抓取、ETL 和 Telegram 投递前安全退出。

**Tech Stack:** Bash、curl、systemd、Docker Compose、Python 3.12、pytest

## Global Constraints

- API 就绪地址固定为 \`http://127.0.0.1:8000/ready\`。
- 总等待时间最多 300 秒；单次请求最多 3 秒；重试间隔最多 5 秒；尝试次数最多 60 次。
- 不修改 systemd unit、timer、Docker Compose、代理、抓取范围、ETL 或 Telegram 投递逻辑。
- API 等待失败时不抓取、不写数据库、不发送 Telegram。
- 不读取、输出或复制 \`REPORT_TRIGGER_TOKEN\`、订阅、节点、Cookie、\`.env\` 或其他敏感值。
- 部署后不自动触发完整日报，避免重复抓取或重复推送。
- Git commit 和 push 必须再次取得用户明确授权；提交信息使用中文。
- 所有 Ubuntu 服务器命令由用户亲自执行。

---

## File Structure

- Modify: \`ops/daily_update.sh\` — 定义 API 就绪等待参数和 \`wait_for_api_ready\`，并在快照检查前调用。
- Modify: \`tests/ops/test_daily_update_script.py\` — 以静态契约测试锁定等待边界、curl 参数和调用顺序。
- Modify after live acceptance: \`docs/project-handoff.md\` — 记录已经真实验收的开机恢复结果和下一步状态，不提前宣称定时推送成功。
- Modify after live acceptance: \`docs/guides/ubuntu-deployment.md\` — 补充 API 就绪等待的排障与验收命令。

### Task 1: 用 TDD 增加 API 就绪等待

**Files:**
- Modify: \`tests/ops/test_daily_update_script.py\`
- Modify: \`ops/daily_update.sh:14-33\`
- Modify: \`ops/daily_update.sh:223-231\`

**Interfaces:**
- Consumes: Ubuntu 主机上的 \`curl\` 和本机 API \`GET http://127.0.0.1:8000/ready\`。
- Produces: \`wait_for_api_ready() -> shell status\`；API 就绪返回 0，等待超时返回 1。

- [ ] **Step 1: 写入失败测试**

在 \`tests/ops/test_daily_update_script.py\` 新增：

\`\`\`python
def test_daily_update_waits_for_api_before_snapshot_checks() -> None:
    text = read_script()

    assert 'API_READY_URL="http://127.0.0.1:8000/ready"' in text
    assert "API_READY_TIMEOUT_SECONDS=300" in text
    assert "API_READY_MAX_ATTEMPTS=60" in text
    assert "API_READY_RETRY_INTERVAL_SECONDS=5" in text
    assert "API_READY_REQUEST_TIMEOUT_SECONDS=3" in text
    assert "wait_for_api_ready()" in text
    assert "curl --fail --silent --output /dev/null" in text
    assert 'request_timeout="$API_READY_REQUEST_TIMEOUT_SECONDS"' in text
    assert '--max-time "$request_timeout"' in text

    function_position = text.index("wait_for_api_ready()")
    call_position = text.index("wait_for_api_ready\n")
    snapshot_position = text.index('if snapshot_exists "$SNAPSHOT_DATE" "$keyword"; then')

    assert function_position < call_position < snapshot_position
    assert 'echo "API 在 5 分钟内未就绪，每日任务停止" >&2' in text
\`\`\`

- [ ] **Step 2: 运行测试并确认它按预期失败**

在 Windows PowerShell 的仓库根目录执行：

\`\`\`powershell
& '<JOBFLOW_PYTHON>' -m pytest tests\ops\test_daily_update_script.py -q
\`\`\`

Expected: 新测试 \`FAILED\`，原因是脚本尚无 \`API_READY_URL\` 或 \`wait_for_api_ready()\`；现有测试仍通过。

- [ ] **Step 3: 实现最小等待函数**

在 \`ops/daily_update.sh\` 的 \`INBOX_DIR\` 之后加入参数：

\`\`\`bash
API_READY_URL="http://127.0.0.1:8000/ready"
API_READY_TIMEOUT_SECONDS=300
API_READY_MAX_ATTEMPTS=60
API_READY_RETRY_INTERVAL_SECONDS=5
API_READY_REQUEST_TIMEOUT_SECONDS=3
\`\`\`

在 \`snapshot_exists\` 之前加入函数：

\`\`\`bash
wait_for_api_ready() {
    local deadline=$((SECONDS + API_READY_TIMEOUT_SECONDS))
    local attempt
    local remaining
    local request_timeout
    local sleep_seconds

    echo "等待 JobFlow API 就绪"

    for ((attempt = 1; attempt <= API_READY_MAX_ATTEMPTS; attempt++)); do
        remaining=$((deadline - SECONDS))
        if ((remaining <= 0)); then
            break
        fi

        request_timeout="$API_READY_REQUEST_TIMEOUT_SECONDS"
        if ((remaining < request_timeout)); then
            request_timeout="$remaining"
        fi

        if curl --fail --silent --output /dev/null \
            --max-time "$request_timeout" \
            "$API_READY_URL"; then
            echo "JobFlow API 已就绪"
            return 0
        fi

        remaining=$((deadline - SECONDS))
        if ((remaining <= 0 || attempt == API_READY_MAX_ATTEMPTS)); then
            break
        fi

        sleep_seconds="$API_READY_RETRY_INTERVAL_SECONDS"
        if ((remaining < sleep_seconds)); then
            sleep_seconds="$remaining"
        fi
        sleep "$sleep_seconds"
    done

    echo "API 在 5 分钟内未就绪，每日任务停止" >&2
    return 1
}
\`\`\`

在 \`cd "$JOBFLOW_DIR"\` 后、\`missing_indexes=()\` 前加入：

\`\`\`bash
wait_for_api_ready
\`\`\`

该调用处于 \`set -e\` 环境：返回 1 时脚本立即退出，因此不会进入快照检查、抓取、ETL 或 Telegram 发送。

- [ ] **Step 4: 运行聚焦测试并确认通过**

\`\`\`powershell
& '<JOBFLOW_PYTHON>' -m pytest tests\ops\test_daily_update_script.py -q
\`\`\`

Expected: \`9 passed\`。

- [ ] **Step 5: 运行完整测试与格式检查**

\`\`\`powershell
& '<JOBFLOW_PYTHON>' -m pytest -q
& '<JOBFLOW_PYTHON>' -m ruff check .
\`\`\`

Expected: 全部 pytest 用例通过；Ruff 输出 \`All checks passed!\`。

- [ ] **Step 6: 自审精确 diff**

\`\`\`powershell
git diff --check -- ops/daily_update.sh tests/ops/test_daily_update_script.py
git diff -- ops/daily_update.sh tests/ops/test_daily_update_script.py
git status --short --branch
\`\`\`

Expected: 只有等待函数、调用点和对应测试属于本任务；不得夹带现有 \`README.md\`、交接文档、\`.superpowers/\` 或其他用户改动。

- [ ] **Step 7: 在明确授权后提交并推送**

先向用户报告测试结果和精确文件列表，并等待用户明确授权。获得授权后才执行：

\`\`\`powershell
git add -- ops/daily_update.sh tests/ops/test_daily_update_script.py docs/archive/specs/2026-08-24-daily-update-api-readiness-design.md docs/archive/plans/2026-08-24-daily-update-api-readiness-implementation.md
git diff --cached --check
git diff --cached --stat
git commit -m "fix: 等待 API 就绪后再运行每日任务"
git push origin main
\`\`\`

Expected: 提交只包含上述四个文件；push 成功；其他未提交文件保持原状。

### Task 2: 服务器部署与非投递验收

**Files:**
- Deploy: \`<JOBFLOW_DIR>/ops/daily_update.sh\`
- Read only: \`/etc/systemd/system/jobflow-daily-update.service\`
- Read only: \`/etc/systemd/system/jobflow-daily-update.timer\`

**Interfaces:**
- Consumes: Task 1 已推送的 Git commit。
- Produces: Ubuntu 上包含等待逻辑的脚本；不启动完整日报。

- [ ] **Step 1: 用户检查服务器工作树**

用户在 Ubuntu 执行：

\`\`\`bash
cd <JOBFLOW_DIR>
git status --short --branch
\`\`\`

Expected: 当前分支可识别；若存在服务器本地改动，停止部署并先截图确认，不覆盖、不 stash、不 reset。

- [ ] **Step 2: 用户拉取已推送提交**

仅在工作树安全时执行：

\`\`\`bash
git pull --ff-only
git log -1 --oneline
\`\`\`

Expected: HEAD 为 \`fix: 等待 API 就绪后再运行每日任务\`；没有 merge commit。

- [ ] **Step 3: 用户做 shell 语法和部署内容检查**

\`\`\`bash
bash -n ops/daily_update.sh
grep -n -A 35 '^wait_for_api_ready' ops/daily_update.sh
grep -n -B 3 -A 3 '^wait_for_api_ready$' ops/daily_update.sh
\`\`\`

Expected: \`bash -n\` 无输出且状态码为 0；能看到等待函数和位于 \`missing_indexes=()\` 之前的调用。

- [ ] **Step 4: 用户确认 API 和定时器，不运行日报**

\`\`\`bash
curl --fail --silent --show-error http://127.0.0.1:8000/ready
systemctl is-active jobflow-daily-update.timer
systemctl list-timers jobflow-daily-update.timer --no-pager
\`\`\`

Expected: \`/ready\` 返回 \`{"status":"ready"}\`；timer 为 \`active\`；下一次触发仍为北京时间 09:00。

- [ ] **Step 5: 用户清除旧失败标记但不启动服务**

\`\`\`bash
sudo systemctl reset-failed jobflow-daily-update.service
systemctl is-failed jobflow-daily-update.service
\`\`\`

Expected: 第二条命令输出 \`inactive\`；没有启动日报、没有 Telegram 消息。

### Task 3: 下一次真实定时运行验收与文档回填

**Files:**
- Modify after evidence: \`docs/project-handoff.md\`
- Modify after evidence: \`docs/guides/ubuntu-deployment.md\`

**Interfaces:**
- Consumes: Task 2 部署后的下一次真实 09:00 定时运行。
- Produces: 可复核的 systemd、日志、Telegram 证据和准确项目状态文档。

- [ ] **Step 1: 用户在 09:00 运行结束后检查服务结果**

\`\`\`bash
systemctl show jobflow-daily-update.service --no-pager \
  -p Result -p ExecMainStatus -p ExecMainStartTimestamp -p ExecMainExitTimestamp
\`\`\`

Expected:

\`\`\`text
Result=success
ExecMainStatus=0
\`\`\`

- [ ] **Step 2: 用户检查本次日志中的等待与完成状态**

\`\`\`bash
journalctl -u jobflow-daily-update.service --since today --no-pager | tail -n 120
\`\`\`

Expected: 包含“等待 JobFlow API 就绪”“JobFlow API 已就绪”和“JobFlow 多关键词每日更新与 Telegram 推送完成”；不再出现由 API 启动竞态造成的“快照状态不确定”。日志含敏感值时先遮挡再分享。

- [ ] **Step 3: 用户确认 Telegram 投递数量**

Expected: 当天只收到一份文字简报和一张配套图。若文字或图片结果不确定，不调用普通发送接口重试，沿用现有人工确认与只补图流程。

- [ ] **Step 4: 根据真实证据更新交接文档**

仅在 Steps 1-3 全部通过后，在 \`docs/project-handoff.md\` 记录：

\`\`\`markdown
- 2026-08-25 已验收每日任务的 API 就绪等待：服务器开机恢复后，脚本先等待 \`/ready\`，再进入快照检查；本次 systemd 结果为 \`success\`、退出码为 0，Telegram 仅收到一份文字和一张图片。
\`\`\`

在 \`docs/guides/ubuntu-deployment.md\` 的每日任务排障区补充：

\`\`\`markdown
每日脚本会在快照检查前等待 \`http://127.0.0.1:8000/ready\`，总等待时间最多 5 分钟。若日志显示“API 在 5 分钟内未就绪”，先检查 \`docker compose ps\`、\`curl http://127.0.0.1:8000/ready\` 和 API 容器日志，不要直接重试 Telegram 发送接口。
\`\`\`

如果真实运行未通过，只记录实际失败证据和下一步，不写成“已稳定推送”。

- [ ] **Step 5: 运行文档检查并等待单独提交授权**

\`\`\`powershell
git diff --check -- docs/project-handoff.md docs/guides/ubuntu-deployment.md
git diff -- docs/project-handoff.md docs/guides/ubuntu-deployment.md
git status --short --branch
\`\`\`

Expected: 文档只陈述已经验收的事实。由于这两个文件当前已有未提交维护内容，提交前必须完整审查 diff，并再次取得用户授权；不得自动提交或推送。
