# JobFlow 项目基础实施计划

> **执行者：学习者本人。** 本计划由学习者在 PowerShell 中逐项执行；Codex 负责解释、验收和代码审查，不代替学习者执行项目命令或提交项目代码。

**目标：** 建立可复现、可测试、可提交的 JobFlow Python 项目基础，为后续 Requests 和 Scrapy 采集模块提供统一工程环境。

**架构：** 第一阶段只建立 Python 包、测试目录、项目元数据和文档结构，不接入爬虫、数据库或 Web 服务。使用 Conda 固定 Python 3.12，使用 `pyproject.toml` 管理项目和开发依赖，使用 pytest 建立测试基线。

**技术栈：** Windows PowerShell、Git、Conda、Python 3.12、pytest、Ruff。

## 全局约束

- 项目根目录固定为 `<LOCAL_JOBFLOW_DIR>`。
- Python 版本固定为 3.12.x；所有 Python 命令在 `jobflow` Conda 环境中执行。
- 源码使用 UTF-8、四空格缩进和 LF/CRLF 均可读的文本格式。
- 第一阶段只安装 pytest 和 Ruff，不提前安装 Scrapy、FastAPI、数据库驱动或 Docker 依赖。
- 不提交 `.env`、密钥、密码、Conda 环境目录、缓存、日志或采集数据。
- 每个任务验收通过后单独提交，不把多个任务压成一次提交。
- 遇到命令输出与计划不一致时停止执行，把完整输出发给 Codex，不盲目继续。

---

## 规划的文件结构

第一阶段结束时结构应为：

```text
<LOCAL_JOBFLOW_DIR>\
├─ docs\
│  ├─ README.md
│  ├─ plans\
│  │  └─ 00-foundation-plan.md
│  └─ specs\
│     └─ 2026-07-11-jobflow-design.md
├─ src\
│  └─ jobflow\
│     └─ __init__.py
├─ tests\
│  └─ test_smoke.py
├─ .gitignore
├─ README.md
└─ pyproject.toml
```

文件职责：

- `src/jobflow/__init__.py`：声明 `jobflow` Python 包和版本号，不放业务逻辑。
- `tests/test_smoke.py`：验证包可导入且版本号符合预期。
- `pyproject.toml`：声明包元数据、Python 版本和开发依赖。
- `.gitignore`：阻止环境、缓存、密钥、日志和数据进入 Git。
- `README.md`：记录项目目标、当前进度和本地开发入口。
- `docs/`：保存规格、计划和后续决策记录。

---

### 任务 1：检查本地开发环境

**涉及文件：**

- 只读： `<LOCAL_JOBFLOW_DIR>\docs\specs\2026-07-11-jobflow-design.md`
- 新建： none
- 修改： none

**输入与输出：**

- 输入： 当前 Windows、Conda、Python、Git 和 Docker 安装状态。
- 输出： 一份发回 Codex 的原始版本检查输出，用于决定是否需要安装或修复工具。

- [ ] **Step 1: 打开新的 PowerShell，进入项目目录**

```powershell
Set-Location <LOCAL_JOBFLOW_DIR>
Get-Location
```

预期结果： 输出路径为 `<LOCAL_JOBFLOW_DIR>`。

- [ ] **Step 2: 检查 Python 与 Conda**

```powershell
python --version
where.exe python
conda --version
conda info --envs
```

预期结果： 每条命令能够正常完成。此时 Python 不必已经是 3.12，因为 任务 3 会新建隔离环境。

- [ ] **Step 3: 检查 Git**

```powershell
git --version
git config --global user.name
git config --global user.email
```

预期结果： Git 能输出版本；用户名和邮箱非空。邮箱可使用 GitHub noreply 邮箱，不必公开私人邮箱。

- [ ] **Step 4: 检查编辑器与 Docker**

```powershell
code --version
docker --version
docker compose version
```

预期结果： VS Code 应能输出版本。Docker 在第一阶段允许未安装或未启动，但必须保留完整错误输出，后续在部署阶段处理。

- [ ] **Step 5: 检查项目当前状态**

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
git status
```

预期结果： 能看到 `docs` 下三份指导文件；`git status` 应提示当前目录尚不是 Git 仓库。这是 任务 2 开始前的正确状态。

- [ ] **Step 6: 将完整输出发给 Codex 验收**

复制 Step 2–5 的原始输出，不要只回复“都正常”。本任务不创建文件、不安装软件、不执行 Git 提交。

**验收门槛：** Codex 明确确认 Python/Conda/Git 可用，并给出 Docker 是否需要立即处理的结论后，才能开始 任务 2。

---

### 任务 2：初始化仓库与文档基线

**涉及文件：**

- 新建： `<LOCAL_JOBFLOW_DIR>\.gitignore`
- 新建： `<LOCAL_JOBFLOW_DIR>\README.md`
- 已有： `<LOCAL_JOBFLOW_DIR>\docs\README.md`
- 已有： `<LOCAL_JOBFLOW_DIR>\docs\plans\00-foundation-plan.md`
- 已有： `<LOCAL_JOBFLOW_DIR>\docs\specs\2026-07-11-jobflow-design.md`

**输入与输出：**

- 输入： 任务 1 验收通过的 Git 安装和身份配置。
- 输出： 使用 `main` 分支的本地 Git 仓库，以及可安全提交的文档基线。

- [ ] **Step 1: 初始化 Git 仓库**

```powershell
Set-Location <LOCAL_JOBFLOW_DIR>
git init -b main
git status --short --branch
```

预期结果： 第一行状态为 `## No commits yet on main`，文档目录显示为未跟踪。

- [ ] **Step 2: 创建 `.gitignore`**

在项目根目录新建 `.gitignore`，完整写入：

```gitignore
# Python bytecode and caches
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.mypy_cache/

# Virtual environments and local configuration
.venv/
venv/
.env
.env.*
!.env.example

# Packaging
build/
dist/
*.egg-info/

# IDE and OS
.vscode/
.idea/
.DS_Store
Thumbs.db

# Runtime output and collected data
logs/
data/raw/
data/processed/
*.log
```

- [ ] **Step 3: 创建根目录 `README.md`**

完整写入：

```markdown
# JobFlow

JobFlow 是一个用于学习数据开发工程的自动化招聘数据采集与分析平台。

## 当前阶段

项目基础环境与测试基线。

## 计划能力

- 多数据源采集与字段标准化
- 定时调度、运行记录与失败重试
- PostgreSQL 幂等入库
- FastAPI 数据查询
- Streamlit 岗位趋势分析
- Docker Compose 本地与云端部署

## 文档

- [项目设计](docs/specs/2026-07-11-jobflow-design.md)
- [实施计划](docs/plans/00-foundation-plan.md)
```

- [ ] **Step 4: 检查敏感文件和暂存内容**

```powershell
git status --short
git check-ignore -v .env
git add .gitignore README.md docs
git diff --cached --stat
```

预期结果：

- `.env` 命中 `.gitignore` 规则。
- 暂存区只包含 `.gitignore`、根 README 和 `docs` 下的 Markdown 文件。
- 不得出现密码、密钥、日志、虚拟环境或数据文件。

- [ ] **Step 5: 创建文档基线提交**

```powershell
git commit -m "docs: add JobFlow design and project guidance"
git status --short --branch
git log -1 --oneline
```

预期结果： 提交成功，工作区干净，分支为 `main`。

**验收门槛：** 将 `git status --short --branch`、`git log -1 --oneline` 和根目录文件列表发给 Codex，确认后开始 任务 3。

---

### 任务 3：创建可复现的 Python 环境

**涉及文件：**

- 新建： `<LOCAL_JOBFLOW_DIR>\pyproject.toml`
- 新建： `<LOCAL_JOBFLOW_DIR>\src\jobflow\__init__.py`

**输入与输出：**

- 输入： 任务 2 中已初始化且干净的 Git 仓库。
- 输出： 名为 `jobflow` 的 Python 3.12 Conda 环境；可通过 editable install 导入的 `jobflow` 包；常量 `jobflow.__version__: str`。

- [ ] **Step 1: 创建并激活 Conda 环境**

```powershell
conda create -n jobflow python=3.12 -y
conda activate jobflow
python --version
where.exe python
```

预期结果： Python 为 `3.12.x`，第一条 Python 路径位于名为 `jobflow` 的 Conda 环境中。

- [ ] **Step 2: 创建 Python 包目录**

```powershell
New-Item -ItemType Directory -Force -Path src\jobflow | Out-Null
```

在 `src/jobflow/__init__.py` 写入：

```python
"""JobFlow package."""

__version__ = "0.1.0"
```

- [ ] **Step 3: 创建 `pyproject.toml`**

完整写入：

```toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "jobflow-learning"
version = "0.1.0"
description = "An automated job data collection and analysis learning project"
readme = "README.md"
requires-python = ">=3.12,<3.13"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=8.3,<9",
    "ruff>=0.9,<1",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
target-version = "py312"
line-length = 100
```

- [ ] **Step 4: 安装当前包和开发依赖**

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -c "import jobflow; print(jobflow.__version__)"
pytest --version
ruff --version
```

预期结果： 包版本输出 `0.1.0`，pytest 和 Ruff 均能输出版本。

- [ ] **Step 5: 检查变更并提交**

```powershell
git status --short
git add pyproject.toml src/jobflow/__init__.py
git commit -m "build: add Python package and development environment"
git status --short --branch
```

预期结果： 提交成功且工作区干净。Conda 环境本身不得出现在 Git 状态中。

**验收门槛：** 将 Python 路径、Python 版本、包版本、pytest 版本、Ruff 版本和 Git 状态发给 Codex，确认后开始 任务 4。

---

### 任务 4：建立测试与代码检查基线

**涉及文件：**

- 新建： `<LOCAL_JOBFLOW_DIR>\tests\test_smoke.py`
- 修改： none

**输入与输出：**

- 输入： `jobflow.__version__: str`，由 任务 3 创建。
- 输出： 一个验证安装和版本协议的自动化测试；全项目 pytest 与 Ruff 基线。

- [ ] **Step 1: 创建测试目录和失败测试**

```powershell
New-Item -ItemType Directory -Force -Path tests | Out-Null
```

先在 `tests/test_smoke.py` 写入一个故意错误的预期值：

```python
import jobflow


def test_package_version() -> None:
    assert jobflow.__version__ == "9.9.9"
```

- [ ] **Step 2: 运行测试并确认它按预期失败**

```powershell
pytest tests/test_smoke.py::test_package_version -v
```

预期结果： `FAILED`，差异中包含实际值 `0.1.0` 和错误预期 `9.9.9`。若测试意外通过或因无法导入而报错，停止并发回完整输出。

- [ ] **Step 3: 修正测试中的预期版本**

将 `tests/test_smoke.py` 中的断言修改为：

```python
assert jobflow.__version__ == "0.1.0"
```

- [ ] **Step 4: 运行测试和静态检查**

```powershell
pytest -v
ruff check .
ruff format --check .
```

预期结果：

- pytest：`1 passed`。
- Ruff check：`All checks passed!`。
- Ruff format check：不报告需要重新格式化的文件。

- [ ] **Step 5: 提交测试基线**

```powershell
git add tests/test_smoke.py
git commit -m "test: add package smoke test"
git status --short --branch
git log --oneline -3
```

预期结果： 工作区干净，最近三次提交依次对应文档基线、Python 环境和测试基线。

**验收门槛：** 将三条检查命令的完整输出及最近三次提交发给 Codex。通过后，进入下一份计划：Requests 招聘数据采集最小纵向切片。

---

## 计划自查结果

- 规格覆盖： 本计划只覆盖项目基础环境，未提前混入采集、数据库、API、调度或部署子系统。
- 文件职责： 每个文件职责单一，源码、测试、配置和文档分离。
- 类型一致性： `jobflow.__version__` 在 任务 3 定义为字符串，在 任务 4 以同一名称和类型消费。
- 安全性： 已明确忽略密钥、环境文件、日志和采集数据。
- 执行顺序： 每个任务都有独立可验证成果和 Git 提交，后续任务只依赖前一任务已定义的接口。
