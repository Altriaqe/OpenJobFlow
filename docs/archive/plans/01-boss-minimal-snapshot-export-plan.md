# BOSS Minimal Snapshot Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Windows 本机通过已审查的第三方工具导出一份最小 BOSS 岗位 JSON 快照，为 JobFlow 后续快照适配器提供真实字段依据。

**Architecture:** 第三方工具安装在 JobFlow 仓库之外，使用独立 Conda 环境和独立 Chrome profile。JobFlow 本任务不修改代码、不接触 Cookie，只在验收时确认输出文件结构、字段名和记录数量。

**Tech Stack:** Windows CMD、Conda、Python 3.12、Chrome CDP、`eatmoreduck/boss-zhipin-scraper` 提交 `26b272f`

## Global Constraints

- 所有命令在 Windows CMD 中执行。
- 外部工具目录为 `<LOCAL_SCRAPER_DIR>`，不得复制进 `<LOCAL_JOBFLOW_DIR>`。
- 使用独立 Conda 环境 `boss-scraper`，不得向 `jobflow` 环境添加第三方工具依赖。
- 只采集 1 页列表并关闭详情页采集。
- 不提交真实岗位快照、Cookie、Token、Chrome profile、请求头或运行日志。
- 遇到验证码、登录限制、拒绝访问或风控提示时停止，不修改工具进行规避。
- 本任务不产生 JobFlow Git 提交。

---

### Task 1: Windows 最小快照导出验证

**Files:**
- External clone: `<LOCAL_SCRAPER_DIR>`
- Local output: `<LOCAL_SCRAPER_DIR>\local-output\boss_jobs.json`
- Modify: none in `<LOCAL_JOBFLOW_DIR>`

**Interfaces:**
- Consumes: 第三方仓库提交 `26b272f`，用户在专用 Chrome 中主动建立的 BOSS 登录状态。
- Produces: UTF-8 JSON 对象；顶层包含 `jobs` 列表，供下一任务根据真实字段设计 JobFlow 快照适配器。

- [ ] **Step 1: 克隆并固定已审查版本**

在 Windows CMD 中运行：

```cmd
cd /d <LOCAL_WORKSPACE_DIR>
git clone https://github.com/eatmoreduck/boss-zhipin-scraper.git
cd /d <LOCAL_SCRAPER_DIR>
git switch --detach 26b272f
git status --short --branch
```

预期最后一行包含：

```text
## HEAD (no branch)
```

如果目标目录已经存在，不要再次克隆，也不要删除目录；停止并先确认该目录的来源和 Git 状态。

- [ ] **Step 2: 创建隔离运行环境**

```cmd
conda create -n boss-scraper python=3.12 -y
conda activate boss-scraper
python --version
```

预期 Python 输出为 `3.12.x`。如果 Conda 提示环境已经存在，改为只运行：

```cmd
conda activate boss-scraper
python --version
```

- [ ] **Step 3: 安装并验证最小依赖**

确保当前目录仍为外部仓库，然后运行：

```cmd
cd /d <LOCAL_SCRAPER_DIR>
python -m pip install -r requirements.txt
python -c "import requests, websocket; print(requests.__version__); print(websocket.__version__)"
```

预期打印 `requests` 和 `websocket-client` 的版本号，不出现 `ModuleNotFoundError`。

- [ ] **Step 4: 启动专用 Chrome 并人工登录**

```cmd
python scripts\boss_cdp_raw.py --setup-chrome
```

预期行为：工具启动使用独立 profile 的 Chrome，并等待用户在该专用窗口中登录 BOSS。不要在截图中展示手机号、二维码、Cookie 或账号信息。

如果命令报告找不到 Chrome、端口冲突、Windows 不支持或登录检测失败，到此停止并保存完整错误文本，不修改第三方脚本。

- [ ] **Step 5: 检查 CDP、依赖和登录状态**

```cmd
python scripts\boss_cdp_raw.py --check
```

预期环境检查中 CDP、依赖和 BOSS 登录状态均成功。出现验证码、拒绝访问或登录失效时停止。

- [ ] **Step 6: 导出一页岗位列表**

```cmd
if not exist local-output mkdir local-output
python scripts\boss_cdp_raw.py --keyword "Python 数据开发" --city 上海 --pages 1 --no-detail --format json --output local-output\boss_jobs.json
```

预期创建：

```text
<LOCAL_SCRAPER_DIR>\local-output\boss_jobs.json
```

本步骤只抓取列表页，不抓取岗位详情。

- [ ] **Step 7: 只检查结构，不打印真实岗位内容**

```cmd
python -c "import json; p=r'local-output\boss_jobs.json'; data=json.load(open(p, encoding='utf-8')); jobs=data.get('jobs', []); print('top_keys=', sorted(data)); print('count=', len(jobs)); print('job_keys=', sorted(jobs[0]) if jobs else [])"
```

验收输出必须满足：

- `top_keys` 中包含 `jobs`。
- `count` 大于 `0`。
- `job_keys` 至少能够看到岗位标题、公司、城市或位置、外部岗位 ID、岗位链接对应的来源字段。
- 终端没有打印 Cookie、Token、完整请求头或具体岗位详情。

- [ ] **Step 8: 提交验收材料**

向导师发送以下内容：

1. `python --version` 输出。
2. `--check` 的非敏感结果。
3. Step 7 的 `top_keys`、`count`、`job_keys` 输出。
4. 若失败，发送从命令开始到报错结束的完整终端文本，但遮盖账号、二维码、Cookie 和 Token。

本任务不修改 JobFlow，因此不运行 JobFlow 的 pytest/Ruff，也不创建 Git 提交。验收通过后，下一任务才会根据真实 `job_keys` 以 TDD 方式编写第一个快照读取测试。
