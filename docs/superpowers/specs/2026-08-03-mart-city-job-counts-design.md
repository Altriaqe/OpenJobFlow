# mart 城市岗位数量视图设计

日期：2026-08-03

## Summary

为 JobFlow 增加第一个 mart 分析指标：统计 core.jobs 中当前全部岗位按城市的数量，供未来只读语义查询 API 和 AI Summary Service 使用。

## Chosen approach

- 指标名称：城市岗位数量（city job count）。
- 统计范围：core.jobs 中当前全部岗位，不限定最近 7 天或 30 天。
- 统计对象：core.jobs 中由 (source, external_id) 唯一确定的当前岗位事实。
- 存储形式：普通 PostgreSQL View，不使用物化视图或聚合表。
- 视图名称：mart.city_job_counts。
- View 动态读取 core.jobs，不需要 Worker 刷新。

## Data model and query semantics

Migration 文件：

~~~text
migrations/004_create_mart_city_job_counts.sql
~~~

视图逻辑：

~~~sql
CREATE SCHEMA IF NOT EXISTS mart;

CREATE OR REPLACE VIEW mart.city_job_counts AS
SELECT
    city,
    COUNT(*) AS job_count
FROM core.jobs
GROUP BY city;
~~~

输出字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| city | TEXT | 岗位所在城市 |
| job_count | BIGINT | 该城市当前岗位数量 |

core.jobs 是事实来源，mart.city_job_counts 只提供聚合结果。View 不保存岗位副本，也不由 Worker 执行刷新。

## Data flow

~~~text
Source Adapter
    ↓
ETL Worker
    ↓
core.jobs
    ↓ 动态 GROUP BY city
mart.city_job_counts
    ↓
只读语义查询 API（后续阶段）
~~~

当 core.jobs 新增或更新后，下一次查询 View 会直接反映新结果。

## Testing and acceptance

1. 离线 migration 契约测试检查 mart schema、View 名称、GROUP BY city 和 COUNT(*)。
2. 真实 PostgreSQL 测试插入两个城市的测试岗位，并验证 View 返回正确数量。
3. 在同一测试中追加一条岗位，不执行刷新操作，再次查询并验证数量变化，证明 View 是动态的。
4. 运行全量 pytest、Ruff、格式检查和 git diff --check。

## Open risks and deferred decisions

- 当前只统计岗位数量，不增加薪资、技能或岗位分类指标。
- 当前不限制时间范围；最近 7 天等时间窗口留给后续语义查询 API。
- 当前不创建物化视图或聚合表；当数据量和查询性能需要时再评估。
- 当前不建设 API、权限白名单或 AI Summary Service。

