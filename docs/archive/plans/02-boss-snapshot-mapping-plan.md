# BOSS Snapshot Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用一个纯函数把 BOSS 快照中的单条岗位字典转换为现有 `JobRecord`，并通过一条合成数据测试固定六个核心字段的映射。

**Architecture:** 映射逻辑放在独立的 BOSS 适配器模块中，不读取文件、不访问网络，也不依赖第三方采集工具。测试只使用人工合成字典；文件读取、损坏 JSON 和缺失字段将在后续微任务中分别实现。

**Tech Stack:** Python 3.12、dataclasses、pytest 8、Ruff

## Global Constraints

- 所有 JobFlow 代码由学生亲手输入。
- 日常命令使用 Windows CMD。
- 本任务不读取或复制真实 `boss_jobs.json`。
- 本任务只覆盖正常记录的六字段映射，不加入文件读取、字段校验、异常包装、薪资解析或数据库逻辑。
- 保持 `JobRecord` 当前六个字段不变。
- 测试必须先红后绿，完成后运行全部 pytest 和 Ruff。

---

### Task 1: 单条 BOSS 岗位映射

**Files:**
- Create: `src/jobflow/adapters/__init__.py`
- Create: `src/jobflow/adapters/boss.py`
- Create: `tests/adapters/test_boss.py`

**Interfaces:**
- Consumes: `JobRecord(source, external_id, title, company, city, detail_url)`；BOSS 合成记录中的 `job_id`、`title`、`boss_name`、`location`、`job_link`。
- Produces: `map_boss_job(raw_job: dict[str, str]) -> JobRecord`。

- [ ] **Step 1: 建立模块和未实现函数**

在 `src/jobflow/adapters/boss.py` 中导入 `JobRecord`，定义下面的接口，并暂时让函数抛出 `NotImplementedError`：

```python
def map_boss_job(raw_job: dict[str, str]) -> JobRecord:
    raise NotImplementedError
```

`src/jobflow/adapters/__init__.py` 保持为空。

- [ ] **Step 2: 编写一条正常映射测试**

在 `tests/adapters/test_boss.py` 中完成以下行为：

1. 导入 `JobRecord` 和 `map_boss_job`。
2. 建立只包含五个来源字段的合成字典：
   - `job_id` 使用 `job-001`。
   - `title` 使用 `Python 数据开发工程师`。
   - `boss_name` 使用 `示例科技`。
   - `location` 使用 `上海·浦东新区·张江`。
   - `job_link` 使用 `https://www.zhipin.com/job_detail/job-001.html`。
3. 调用 `map_boss_job(raw_job)`。
4. 构造预期 `JobRecord`：`source` 为 `boss_zhipin`，`city` 为 `上海`，其余字段按映射表取值。
5. 使用 `assert actual == expected` 比较两个 dataclass 实例。

测试函数命名为：

```python
def test_map_boss_job_returns_job_record() -> None:
```

- [ ] **Step 3: 运行测试确认红灯**

```cmd
pytest tests\adapters\test_boss.py -q
```

预期测试因 `NotImplementedError` 失败。若失败原因是导入错误、语法错误或文件路径错误，先修正测试结构，不能把它当作有效红灯。

- [ ] **Step 4: 完成最小映射**

只在 `map_boss_job()` 中返回一个 `JobRecord`，使用下表，不加入额外分支：

| JobRecord 字段 | 值 |
|---|---|
| `source` | 固定字符串 `boss_zhipin` |
| `external_id` | `raw_job["job_id"]` |
| `title` | `raw_job["title"]` |
| `company` | `raw_job["boss_name"]` |
| `city` | `raw_job["location"]` 按第一个 `·` 分隔后的第一段 |
| `detail_url` | `raw_job["job_link"]` |

- [ ] **Step 5: 运行定向测试确认绿灯**

```cmd
pytest tests\adapters\test_boss.py -q
```

预期：

```text
1 passed
```

- [ ] **Step 6: 运行项目质量检查**

```cmd
pytest -q
ruff check .
ruff format --check .
```

预期：全部测试通过，Ruff 无检查和格式错误。原有测试为 6 条，因此完成后应为 `7 passed`。

- [ ] **Step 7: 检查差异并提交**

```cmd
git diff -- src\jobflow\adapters tests\adapters
git status --short
git add src\jobflow\adapters tests\adapters
git commit -m "feat: 添加 BOSS 岗位字段映射"
```

提交前确认没有真实 JSON、Cookie、Token、Chrome profile 或第三方仓库文件进入 JobFlow。
