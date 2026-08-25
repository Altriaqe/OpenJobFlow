# JobFlow Production ETL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有招聘快照适配器逐步建设为可部署的 ETL、轻量数仓、只读 API 与聚合分析平台。

**Architecture:** Source Adapter 将不同来源转换为统一数据契约，独立 Worker 完成 raw/core/mart 分层和幂等入库，FastAPI 与 Streamlit 只读取公开聚合指标。第一版使用 PostgreSQL、APScheduler 和 Docker Compose；dbt 与 Airflow 延后到满足升级条件时再引入。

**Tech Stack:** Python 3.12、pytest、Ruff、PostgreSQL、SQLAlchemy、Alembic、APScheduler、FastAPI、Streamlit、Docker Compose、GitHub Actions

## Global Constraints

- 项目代码由学生亲手编写，导师提供结构提示、检查点和排错指导。
- 每次执行一个 1–3 小时的完整能力，可包含 2–4 个相关测试，能力完成后统一提交。
- 日常使用 Windows CMD；CI 和容器使用 Linux。
- BOSS 原始快照、Cookie、Token 和招聘者信息不得提交 Git 或上传公网。
- 公网只提供聚合分析、健康检查和 OpenAPI 文档。
- CI 不访问 BOSS 或真实外部网络。
- 具体字段、指标和性能数字必须来自真实实现与测量，不预先编造。

---

### Milestone 1: 数据接入与质量边界

**Files:** `src/jobflow/adapters/`、`src/jobflow/models/`、`tests/adapters/`、`tests/models/`

**Produces:** 经过结构和必要字段校验的统一岗位记录，以及批量成功、拒绝和错误统计。

- [ ] 校验快照顶层存在 `jobs` 且其值为列表。
- [ ] 校验列表元素为字典，并对错误记录给出可定位信息。
- [ ] 根据真实快照扩展薪资、经验、学历和技能字段。
- [ ] 为必要字段缺失和错误类型建立数据质量错误。
- [ ] 保持所有单元测试不访问真实网络或真实快照。

### Milestone 2: PostgreSQL 与迁移基础

**Files:** `compose.yaml`、`src/jobflow/db/`、`migrations/`、`tests/integration/`

**Produces:** 可由 Docker 启动并通过 Alembic 重建的 `ops/raw/core/mart` 数据库结构。

- [ ] 增加 PostgreSQL Compose 服务和健康检查。
- [ ] 配置环境变量与 `.env.example`。
- [ ] 建立 SQLAlchemy engine、session 和事务边界。
- [ ] 使用 Alembic 创建 `ops`、`raw`、`core`、`mart` Schema 与第一批表。
- [ ] 使用真实 PostgreSQL 验证 migration、唯一约束和回滚。

### Milestone 3: 幂等 ETL 与运行追踪

**Files:** `src/jobflow/etl/`、`src/jobflow/repositories/`、`tests/etl/`、`tests/integration/`

**Produces:** 从 Adapter 到 raw/core 的可重复运行 ETL，重复批次不产生重复岗位。

- [ ] 创建和更新 `ingestion_runs`。
- [ ] 保存 raw JSONB、批次、哈希和质量状态。
- [ ] 对 `(source, external_id)` 执行 PostgreSQL Upsert。
- [ ] 正确维护 `first_seen_at`、`last_seen_at` 和内容哈希。
- [ ] 记录输入、有效、拒绝、新增和更新数量。

### Milestone 4: 清洗与核心模型

**Files:** `src/jobflow/cleaning/`、`src/jobflow/quality/`、`tests/cleaning/`、`tests/quality/`

**Produces:** 可解释的城市、薪资、经验、学历与技能标准化结果。

- [ ] 保留原始薪资并解析上下限、周期和额外薪数。
- [ ] 标准化城市与区域。
- [ ] 使用词典和规则提取技能。
- [ ] 将不可解析记录隔离并记录原因。
- [ ] 为每项分析指标记录口径和限制。

### Milestone 5: Gold 数据集市

**Files:** `src/jobflow/marts/`、`sql/marts/`、`tests/marts/`

**Produces:** 城市、薪资和技能三个公开指标集。

- [ ] 构建 `city_job_daily`。
- [ ] 构建 `salary_band_daily`。
- [ ] 构建 `skill_demand_daily`。
- [ ] 验证重复刷新结果一致。
- [ ] 编写指标口径文档。

### Milestone 6: FastAPI 只读服务

**Files:** `src/jobflow/api/`、`tests/api/`

**Produces:** `/health`、`/ready` 和三个 `/analytics` 聚合接口及 OpenAPI 文档。

- [ ] 配置应用、依赖注入和数据库连接生命周期。
- [ ] 实现健康与就绪检查。
- [ ] 实现城市、薪资和技能聚合接口。
- [ ] 增加参数校验、最大返回数量和安全错误响应。
- [ ] 证明公共接口无法访问 raw/core 私有数据。

### Milestone 7: Streamlit 公共作品站

**Files:** `src/jobflow/dashboard/`、`tests/dashboard/`

**Produces:** 通过 FastAPI 获取数据的概览、城市、薪资和技能分析页面。

- [ ] 展示来源、更新时间和数据口径。
- [ ] 展示城市趋势、薪资分布和技能需求。
- [ ] 对 API 不可用和空数据提供明确状态。
- [ ] 不直接读取 raw 数据或数据库密钥。

### Milestone 8: Worker、调度与可观测性

**Files:** `src/jobflow/worker/`、`src/jobflow/cli/`、`tests/worker/`

**Produces:** `jobflow ingest`、`jobflow worker`、单来源任务锁、结构化日志和失败恢复。

- [ ] 建立 CLI 入口和来源注册表。
- [ ] 将 APScheduler 运行在独立 Worker 服务。
- [ ] 防止同一来源任务重叠。
- [ ] 日志携带 run ID、来源、阶段、数量、耗时和错误类型。
- [ ] Worker 重启后不重复处理成功批次。

### Milestone 9: Docker、CI 与云端验收

**Files:** `Dockerfile`、`compose.yaml`、`.github/workflows/`、部署与运行文档

**Produces:** 可复现的四服务部署、自动质量检查和公共作品站。

- [ ] Compose 启动 postgres、worker、api 和 dashboard。
- [ ] 容器启动时安全执行 migration。
- [ ] GitHub Actions 运行 pytest、Ruff 和部署 smoke test。
- [ ] 配置生产环境变量、持久化、备份和恢复说明。
- [ ] 云端连续运行七天并记录真实数据量、耗时和 API 响应时间。

## Execution Mode

本路线由学生在当前会话中按导师检查点执行，不使用子代理代写代码。阶段顺序固定，每日任务根据仓库状态和可用时间动态调整；只有架构变化和阶段总结更新文档。
