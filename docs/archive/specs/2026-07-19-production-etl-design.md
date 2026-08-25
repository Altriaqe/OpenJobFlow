# JobFlow 生产化 ETL 与分析平台设计

日期：2026-07-19

## 目标与定位

JobFlow 是一个面向数据开发实习作品集的招聘数据 ETL、查询与趋势分析平台。项目以数据开发为主、数据分析为辅，训练并展示数据源接入、质量校验、增量处理、关系建模、任务调度、数据服务、分析展示和云端部署能力。

第一版产品是公共只读作品站：匿名用户可以访问聚合分析、健康检查和 OpenAPI 文档；采集、文件导入、调度配置和数据库写操作只允许后台 Worker 或命令行执行。

本设计取代 `2026-07-11-jobflow-design.md` 中将 Scrapy/Scrapyd 作为核心运行链路的方案。Scrapy 保留为可选 Source Adapter；Scrapyd 不作为第一版硬依赖。

## 选定架构

采用“ETL 优先的模块化单体 + PostgreSQL 轻量数仓分层”：

```text
数据源
├─ 本机 BOSS 快照
├─ 本地模拟 API
├─ 合规公开数据
├─ 未来商用 API
└─ 可选 Scrapy Spider
        │
        ▼
Source Adapter
        │
        ▼
ETL Worker
├─ 采集或导入
├─ 结构与字段校验
├─ 清洗和标准化
├─ 质量统计
├─ 幂等 Upsert
└─ 运行日志
        │
        ▼
PostgreSQL
├─ ops：运行与调度元数据
├─ raw：Bronze 原始数据
├─ core：Silver 统一数据
└─ mart：Gold 聚合指标
        │
        ▼
FastAPI 只读接口
        │
        ▼
Streamlit 公共作品站
```

Docker Compose 第一版包含 `postgres`、`worker`、`api` 和 `dashboard` 四个服务。APScheduler 运行在单独 Worker 中，不放入 FastAPI 进程。dbt 作为核心系统上线后的增强项；Airflow 仅在任务数量和依赖复杂度明显增加后评估。

## 数据源与合规边界

本机可以使用外部 `boss-zhipin-scraper` 生成的快照验证真实 ETL，但该工具不并入 JobFlow，不随云端服务部署。BOSS 原始快照、Cookie、Token、Chrome profile 和招聘者信息不得提交 Git、上传公网或由公共 API 返回。

获得商用 API 前，公网主要展示本机 ETL 生成的城市、薪资和技能聚合结果，或使用明确允许展示的公开数据。获得商用 API 后，仅新增或替换 Source Adapter，数据库、API 和分析层保持不变。

公网不提供单条 BOSS 岗位详情、原始快照下载、任意文件上传、任意 SQL、启动采集任务或调度配置接口。所有公开指标保留来源、更新时间和口径说明，并支持按来源删除。

## PostgreSQL 分层

### ops

第一版核心表：

- `ops.data_sources`：来源名称、类型、启用状态、配置引用和最近运行时间。
- `ops.ingestion_runs`：运行状态、开始与结束时间、输入/有效/拒绝/写入数量、耗时、错误摘要和批次校验值。

### raw / Bronze

`raw.job_records` 保存运行批次、来源、外部岗位 ID、原始 JSONB、内容哈希、采集时间、校验状态和质量错误代码。原始数据尽量保持不可变；无效记录不能静默丢弃，必须能够追溯到批次和记录。

BOSS raw 数据仅在本地环境保存；云端 raw 层只接收获得授权或明确允许使用的数据。

### core / Silver

核心表包括：

- `core.jobs`
- `core.skills`
- `core.job_skills`

`core.jobs` 逐步包含来源、外部 ID、标题、公司、城市、区域、原始薪资、薪资上下限、薪资周期、经验、学历、详情链接、描述、发布时间、首次发现、最后发现、内容哈希和有效状态。

幂等键为 `(source, external_id)`。重复导入不新增重复岗位，只更新允许变化的字段、内容哈希和 `last_seen_at`，并保留 `first_seen_at`。

薪资必须保留原文、上下限和周期。日薪、月薪、年薪和面议不能在没有明确规则时强制转换为同一月薪口径。

### mart / Gold

第一版只构建三个指标集：

- `mart.city_job_daily`：城市岗位数量和趋势。
- `mart.salary_band_daily`：薪资区间分布。
- `mart.skill_demand_daily`：技能出现次数和趋势。

第一版使用 PostgreSQL View 或 Materialized View；指标稳定后再由 dbt 管理转换、测试和血缘。

## ETL 运行流程

```text
创建 ingestion_run
→ Source Adapter 获取数据
→ 写入 raw
→ 结构与字段校验
→ 转换为 core 模型
→ 事务内幂等 Upsert
→ 刷新 mart
→ ingestion_run 标记成功
```

失败时记录来源、运行 ID、失败阶段、异常类型、数量和耗时，回滚当前事务并将运行状态标记为 `failed`。同一来源已有任务运行时拒绝重复启动。

第一版后台入口为 `jobflow ingest ...` 和 `jobflow worker`。Worker 负责 APScheduler 和 ETL，不对公网开放。

## API 与安全

FastAPI 第一版只开放：

- `/health`
- `/ready`
- `/analytics/cities`
- `/analytics/salaries`
- `/analytics/skills`
- OpenAPI 文档

数据库密码和 API 密钥使用环境变量，仓库只提供 `.env.example`。日志不得记录 Cookie、Token、完整连接串或生产堆栈。CORS 只允许仪表盘域名，公共接口设置参数校验、最大返回数量和基础限流。

`/health` 检查进程，`/ready` 检查数据库连接和迁移状态。生产数据使用 Volume 或托管 PostgreSQL 持久化，并提供备份和恢复说明。

## 测试策略

- 单元测试：适配器、结构与字段校验、薪资、城市、技能、哈希和质量规则。
- PostgreSQL 集成测试：migration、唯一约束、Upsert、事务回滚和时间字段。
- API 测试：健康检查、参数校验、聚合接口和私有数据边界。
- 端到端测试：模拟数据源经过 Worker、raw、core、mart 后能被 API 查询。
- 部署测试：Docker Compose 启动、migration、服务健康和 Dashboard 可访问。

CI 不连接 BOSS 或真实外部网络；真实 BOSS 快照只做人工 smoke test。优先覆盖清洗、幂等、事务、状态流转和错误分支，不追求虚高覆盖率。

## 学习与实施阶段

按顺序推进，但不绑定固定日历：

1. 数据接入与质量边界：快照结构、必要字段、统一模型和批量统计。
2. PostgreSQL 与分层：Docker、Schema、SQLAlchemy、Alembic、唯一约束和 Upsert。
3. 清洗与质量：城市、薪资、技能、无效记录隔离和内容哈希。
4. 数据集市：城市、薪资和技能指标及口径文档。
5. FastAPI：只读聚合接口、健康检查和连接池。
6. Streamlit：概览、趋势、分布、更新时间和口径说明。
7. Worker 与调度：CLI、APScheduler、任务锁、日志和恢复。
8. Docker、CI 与云端：Compose、环境变量、GitHub Actions、部署和备份。
9. 后期增强：dbt、商用 API、增量模型；满足升级条件后再评估 Airflow。

## 导师式协作协议

每天开始先检查 Git、最近提交、pytest、Ruff 和未完成内容，再发布一个 1–3 小时内可验收的完整能力。任务可以包含 2–4 个相关测试，中间按 TDD 检查，能力完成后统一提交一次。

每个任务说明目标、原因、知识点、文件位置、编写顺序、结构提示、Windows CMD 命令、预期结果、验收标准和 Git 提交。项目代码由学生亲手编写；指导者不直接交付完整实现。每日进度可以不同，时间不足时停在安全检查点。只有关键架构变化和阶段总结才写文档，不为每个小步骤创建计划文件。

## 完成标准与简历呈现

完成时必须满足：新环境可按 README 启动；Docker Compose 一键运行；migration 可重复执行；重复 ETL 不产生重复岗位；错误可追溯到批次；公网只返回聚合数据；API、Dashboard 和 CI 可用；关键指标有口径文档；云端连续运行至少七天；核心模块能够现场解释。

简历只使用真实测量的记录数、拒绝比例、Upsert 数量、ETL 耗时、API 响应时间、测试数量和连续运行天数。不得声称独立破解 BOSS 反爬、使用 BOSS 官方 API、获得平台授权，或编造尚未测量的数据。
