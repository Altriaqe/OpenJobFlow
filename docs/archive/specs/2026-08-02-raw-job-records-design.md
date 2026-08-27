# raw 原始岗位记录层设计

日期：2026-08-02

## Summary

为 JobFlow 增加 `raw` 原始数据层。它保存每次采集到的原始岗位内容，供追溯、排错和后续重新处理使用；`core.jobs` 继续保存清洗、映射后的岗位事实。

## Chosen approach

- 一条原始岗位对应 `raw.job_records` 中的一行。
- 每个批次都保存一份观察记录；同一岗位在不同批次出现时保留历史。
- 使用 `payload JSONB` 保存完整原始 JSON，不提前拆解或丢弃来源字段。
- 使用 `(batch_id, source, external_id)` 唯一约束，防止同一批次重复记录。
- `run_job_batch(raw_jobs, jobs)` 同时接收原始字典列表和标准 `JobRecord` 列表。
- raw 与 core 在同一个岗位批次事务中写入。批次开始记录先单独提交，成功或失败状态再单独提交。

## Data model

```text
ops.batches（一批 ETL 运行）
        │
        ├── raw.job_records（本批次原始岗位）
        │
        └── core.jobs（清洗后的岗位事实）
```

`raw.job_records` 字段：

| 字段 | 约束 | 作用 |
| --- | --- | --- |
| `id` | identity primary key | 原始记录内部 ID |
| `batch_id` | not null, foreign key | 关联所属 ETL 批次 |
| `source` | not null | 数据来源 |
| `external_id` | not null | 来源平台岗位编号 |
| `payload` | not null JSONB | 完整原始岗位内容 |
| `ingested_at` | not null, default current timestamp | 写入原始层的时间 |

## Data flow and transaction behavior

```text
load_boss_jobs()
    ↓ raw_jobs
map_boss_jobs(raw_jobs)
    ↓ jobs
run_job_batch(raw_jobs, jobs)
    ├─ start_batch() → commit running
    ├─ insert raw.job_records
    ├─ insert core.jobs
    ├─ finish_batch() → commit succeeded
    └─ exception → rollback raw/core
                  → fail_batch() → commit failed
                  → re-raise original exception
```

raw 和 core 必须一起成功或一起回滚，避免当前阶段出现半完成批次。后续如果需要失败原始数据重放，可以再拆分独立的 raw ingestion 阶段。

## Testing and acceptance

1. raw 数据库函数单元测试验证目标表、参数化 SQL 和原始 JSON 不被修改。
2. migration 的真实 PostgreSQL 测试验证 schema、外键、同批次唯一约束和跨批次历史记录。
3. Worker 成功集成测试验证批次为 `succeeded`，raw 和 core 均有数据，`row_count` 正确。
4. Worker 失败测试验证 raw/core 一起回滚，批次为 `failed`，原始异常继续向外传播。
5. 完成后运行全量 pytest、Ruff、格式检查和 `git diff --check`。

## Open risks and deferred decisions

- 当前 raw 表先保存完整 JSONB，不提前设计来源专属字段索引。
- 当前方案不单独实现失败 raw 数据重放；这是后续阶段的能力。
- 具体 JSONB 适配方式、migration 编号和函数命名留到实现计划中确定，并遵循现有项目风格。

