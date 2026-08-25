# BOSS Snapshot Loading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从用户指定的 UTF-8 JSON 快照中读取顶层 `jobs` 列表，为后续批量映射提供来源记录。

**Architecture:** 文件读取函数与现有单条映射函数放在同一个 BOSS 适配器模块中，但二者保持独立：读取函数只返回来源字典列表，映射函数只处理单条字典。本任务只覆盖正常快照；文件不存在、损坏 JSON 和结构错误将在后续微任务中分别建立异常边界。

**Tech Stack:** Python 3.12、`pathlib`、标准库 `json`、pytest 8、Ruff

## Global Constraints

- 所有 JobFlow 代码由学生亲手输入。
- 日常命令使用 Windows CMD。
- 测试只使用 pytest `tmp_path` 生成的临时合成快照，不读取或复制真实 `boss_jobs.json`。
- 本任务只读取顶层 `jobs` 列表，不进行字段映射、清洗、校验、去重或入库。
- 不改变现有 `map_boss_job(raw_job: dict[str, str]) -> JobRecord` 行为。
- 测试必须先红后绿，完成后运行全部 pytest 和 Ruff。

---

### Task 1: 正常 BOSS 快照读取

**Files:**
- Modify: `src/jobflow/adapters/boss.py`
- Modify: `tests/adapters/test_boss.py`

**Interfaces:**
- Consumes: `pathlib.Path` 指向的 UTF-8 JSON 文件，顶层为对象并包含 `jobs` 列表。
- Produces: `load_boss_jobs(path: Path) -> list[dict[str, str]]`。

- [ ] **Step 1: 定义未实现的读取接口**

在 `src/jobflow/adapters/boss.py` 顶部导入 `Path`，并在现有映射函数下方定义 `load_boss_jobs()`。参数名为 `path`，参数类型为 `Path`，返回类型为来源字典列表；函数体暂时抛出 `NotImplementedError`。

- [ ] **Step 2: 准备临时合成快照测试**

在 `tests/adapters/test_boss.py` 中新增 `json` 和 `Path` 所需导入，并导入 `load_boss_jobs`。新增测试 `test_load_boss_jobs_returns_jobs_list(tmp_path: Path) -> None`，按以下顺序完成：

1. 建立一条只含 `job_id`、`title`、`boss_name`、`location` 和 `job_link` 的合成来源字典。
2. 把该字典放入列表，并以 `{"jobs": 合成列表}` 作为顶层结构。
3. 使用 `tmp_path / "boss_jobs.json"` 得到临时文件路径。
4. 使用标准库 `json` 把顶层结构序列化为包含中文的 JSON 文本。
5. 用 UTF-8 将文本写入临时文件。
6. 调用 `load_boss_jobs()`。
7. 断言实际结果等于原来的合成列表。

- [ ] **Step 3: 运行测试确认红灯**

```cmd
pytest tests\adapters\test_boss.py::test_load_boss_jobs_returns_jobs_list -q
```

预期测试因 `NotImplementedError` 失败。导入错误、语法错误和路径错误不算有效红灯。

- [ ] **Step 4: 完成最小读取实现**

在 `src/jobflow/adapters/boss.py` 中使用标准库 `json` 和 `Path.read_text(encoding="utf-8")`：

1. 读取 `path` 指向的 UTF-8 文本。
2. 将 JSON 文本解析成 Python 顶层对象。
3. 返回顶层对象中键 `jobs` 对应的列表。

本步骤不捕获任何异常，也不逐条调用 `map_boss_job()`。

- [ ] **Step 5: 运行适配器测试确认绿灯**

```cmd
pytest tests\adapters\test_boss.py -q
```

预期：

```text
2 passed
```

- [ ] **Step 6: 运行项目质量检查**

```cmd
pytest -q
ruff check .
ruff format --check .
```

预期：全部测试通过，Ruff 无检查和格式错误。原有测试为 7 条，因此完成后应为 `8 passed`。

- [ ] **Step 7: 格式化、复验并提交**

如果格式检查要求调整，只格式化本任务修改的两个文件，然后重新运行 Step 6。通过后检查差异，确认没有真实快照或敏感文件，再提交：

```cmd
git add src\jobflow\adapters\boss.py tests\adapters\test_boss.py
git diff --cached --check
git diff --cached
git commit -m "feat: 添加 BOSS 快照读取函数"
```
