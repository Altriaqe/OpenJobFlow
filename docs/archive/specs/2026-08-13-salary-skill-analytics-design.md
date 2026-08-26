# JobFlow 薪资与技能分析设计

**日期：** 2026-08-13

**状态：** 已完成方案确认，待实施

**范围：** BOSS 快照适配、统一岗位模型、PostgreSQL core/mart、FastAPI 只读分析接口

## 一、目标

在现有城市岗位数量链路上，补齐第一批有业务价值的岗位字段，让 JobFlow 能够回答：

- 不同城市的月薪范围如何；
- 当前岗位最常要求哪些技能。

本阶段先完善数据层和固定只读分析接口，不接入 AI 总结或企业微信发送。

## 二、真实来源依据

本设计基于本地 BOSS JSON 快照的只读字段审查。快照共有 30 条岗位，相关字段情况如下：

| 来源字段 | 完整情况 | 用途 |
| --- | --- | --- |
| `salary` | 30/30 非空 | 薪资原文与结构化解析 |
| `salary_source` | 30/30 非空 | 来源追溯，当前均为 `api` |
| `skills` | 25/30 非空 | 第一版技能统计的唯一来源 |
| `job_labels` | 30/30 非空 | 岗位标签，本阶段暂不参与技能统计 |
| `tags` | 30/30 非空 | 经验和学历组合，本阶段暂不解析 |

已发现的薪资格式只有：

- `N-NK`；
- `N-NK·N薪`；
- `N-N元/天`。

设计不推测快照中不存在的岗位描述、发布时间等字段。

## 三、选定方案

在 `core.jobs` 中直接增加标准化薪资字段和技能数组：

```text
salary_text
salary_min
salary_max
salary_unit
salary_months
skills TEXT[]
```

第一版不建立技能维表和岗位技能关系表。当前数据规模小，PostgreSQL 数组配合 `unnest()` 足以支持热门技能统计；未来出现技能别名、技能分类或复杂关联需求时，再演进为独立维表。

## 四、统一模型与清洗规则

`JobRecord` 与 `core.jobs` 增加：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `salary_text` | `str` / `TEXT` | 来源薪资原文，用于追溯 |
| `salary_min` | `int` / `INTEGER` | 薪资下限 |
| `salary_max` | `int` / `INTEGER` | 薪资上限 |
| `salary_unit` | `str` / `TEXT` | `K_PER_MONTH` 或 `CNY_PER_DAY` |
| `salary_months` | `int | None` / `SMALLINT` | `·N薪` 的月数，无该信息时为空 |
| `skills` | `list[str]` / `TEXT[]` | 清洗后的技能列表 |

薪资映射：

```text
15-25K
-> min=15, max=25, unit=K_PER_MONTH, months=NULL

15-25K·14薪
-> min=15, max=25, unit=K_PER_MONTH, months=14

200-300元/天
-> min=200, max=300, unit=CNY_PER_DAY, months=NULL
```

约束：

- 保留 `salary_text`，结构化结果必须可追溯；
- `salary_min`、`salary_max` 必须大于零；
- `salary_min` 不得大于 `salary_max`；
- `salary_unit` 只允许 `K_PER_MONTH`、`CNY_PER_DAY`；
- `salary_months` 仅适用于月薪，存在时必须大于零；
- 日薪不按固定工作天数换算为月薪；
- `skills` 按 `|` 拆分、去除首尾空格、删除空项，并保持原顺序去重；
- 空技能字符串映射为空列表，不映射为 `NULL`；
- 第一版不进行技能别名合并。

## 五、组件职责与数据流

```text
raw.job_records
  保存来源原文，不修改
        |
        v
BOSS Adapter
  parse_salary() + parse_skills()
        |
        v
JobRecord
  统一结构化字段
        |
        v
core.jobs
  Upsert 当前岗位状态
        |
        v
mart Views
  固定薪资和技能统计口径
        |
        v
FastAPI
  固定只读 HTTP 契约
```

职责边界：

- `load_boss_jobs()` 负责文件读取、顶层结构和来源字段校验；
- `parse_salary()` 是纯函数，只解析已支持的薪资格式；
- `parse_skills()` 是纯函数，只清洗技能字符串；
- `map_boss_job()` 组合来源字段并创建 `JobRecord`；
- `insert_job()` 只执行参数化 SQL，不解析来源文本；
- mart View 固定业务指标口径；
- FastAPI 路由只调用固定查询函数，不接受任意 SQL、表名或字段名。

## 六、错误处理

- `salary` 缺失、为空或格式无法识别：抛出 `SnapshotError`；
- `skills` 字段缺失：抛出 `SnapshotError`；
- `skills` 是空字符串：合法，结果为空列表；
- 解析或写入失败时，沿用现有 Worker 事务：raw/core 写入回滚，批次记录为 `failed` 并保存失败原因；
- API 数据库异常返回 `503` 和通用错误信息，不暴露连接参数、SQL 或 traceback。

## 七、数据库迁移与历史数据

新增 `005` migration：

- 为 `core.jobs` 增加薪资与技能字段；
- 增加薪资范围、单位和月数约束；
- 创建 `mart.city_salary_stats`；
- 创建 `mart.skill_job_counts`。

为兼容迁移前的 `core.jobs` 记录，薪资字段初始允许 `NULL`，`skills` 使用空数组作为默认值。迁移不伪造历史薪资；迁移后重新运行真实快照 ETL，通过现有 Upsert 补齐当前岗位的薪资和技能。历史 `raw.job_records.payload` 不修改。

新增业务字段必须参与 Upsert 的内容变化判断；薪资或技能变化时更新 `updated_at`，内容未变化时只更新 `last_seen_at`。

## 八、mart 指标

### 城市月薪统计

`mart.city_salary_stats` 只统计 `salary_unit = 'K_PER_MONTH'` 且上下限完整的岗位，返回：

- `city`；
- `job_count`；
- `avg_salary_min`；
- `avg_salary_max`；
- `avg_salary_mid`。

平均值单位均为 K/月。日薪岗位不参与该 View，不做隐式换算。结果按岗位数降序、城市名升序。

### 热门技能统计

`mart.skill_job_counts` 使用 `unnest(skills)` 展开技能数组，返回：

- `skill`；
- `job_count`。

空数组不产生统计行。结果按岗位数降序、技能名升序。

## 九、只读 API

### 城市薪资

```http
GET /analytics/salaries/cities?limit=20
```

响应项包含 `city`、`job_count`、`avg_salary_min`、`avg_salary_max`、`avg_salary_mid`。

### 热门技能

```http
GET /analytics/skills?limit=20
```

响应项包含 `skill`、`job_count`。

共同契约：

- `limit` 默认 20，允许范围 1 到 100；
- 空数据返回 `200` 和 `[]`；
- 参数越界返回 `422`；
- 数据库异常返回 `503`；
- 第一版不提供薪资筛选、技能搜索、任意排序或动态查询。

## 十、测试与验收

测试顺序：

1. 薪资解析单元测试覆盖三种真实格式和非法格式；
2. 技能清洗单元测试覆盖拆分、空格、重复项和空字符串；
3. Adapter 测试验证完整 `JobRecord`；
4. 数据库单元测试验证新增 SQL 参数和内容变化判断；
5. 真实 PostgreSQL 集成测试验证列、约束、Upsert 和事务回滚；
6. mart 测试验证日薪排除、技能展开和稳定排序；
7. API 测试验证 `200`、`422`、`503`；
8. 全量测试与 Ruff 回归，确保已有城市统计 API 和 ETL 行为不退化。

完成标准：

- 真实快照能够完整进入 raw/core；
- 月薪与日薪不混算；
- 技能统计仅来源于 `skills`；
- 两个 mart View 返回稳定、正确的结果；
- 两个新 API 通过离线测试和真实 PostgreSQL 验收；
- 全量测试与 Ruff 通过；
- 仓库不包含真实快照、Cookie、Token 或其他敏感信息。

## 十一、明确不在本阶段处理的内容

- AI Summary Service 与企业微信发送；
- 日薪到月薪的换算；
- 技能别名归一化和技能维表；
- 经验、学历、岗位描述、发布时间；
- 任意查询、任意排序和动态 SQL；
- 云端部署与持续调度。
