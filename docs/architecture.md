# OpenJobFlow 系统架构

更新日期：2026-10-18

OpenJobFlow 是一个面向自托管场景的招聘数据处理与分析项目。它把数据采集、ETL、PostgreSQL 分层存储、固定分析接口、报告生成和外部投递拆成独立边界，便于替换数据源、定位故障和按需启用渠道。

## 1. 项目定位

### 1.1 项目名称

- 公开项目名：`OpenJobFlow`
- GitHub 仓库：`Altriaqe/OpenJobFlow`
- Python 包名：`jobflow`（为保持代码和配置兼容，暂不改名）

### 1.2 目标

- 将合规取得的岗位 JSON 快照标准化并写入 PostgreSQL；
- 提供固定范围、只读、可复现的分析接口；
- 生成查询简报、趋势图和可选的 AI 摘要；
- 独立支持 Telegram 消息和微信公众号待审核草稿；
- 为 Ubuntu 自托管部署提供每日任务编排和故障边界。

### 1.3 明确不属于项目范围

- 不提供第三方数据授权，不绕过登录、验证码、风控或访问限制；
- 不把真实抓取数据、账号凭据、Cookie、代理订阅或服务器私有配置提交到仓库；
- 不宣称公网高可用、自动恢复上游登录态或无人值守长期稳定；
- 微信链路只自动创建待审核草稿，正式发布仍由维护者人工确认。

## 2. 总体架构

```text
systemd timer
    │
    ▼
ops/daily_update.sh
    │
    ├─ 合规快照 / 外部采集器
    │       │
    │       ▼
    ├─ Source Adapter：校验、映射、薪资与技能标准化
    │       │
    │       ▼
    ├─ ETL Worker：批次、事务、raw/core 写入
    │       │
    │       ▼
    └─ PostgreSQL：ops / raw / core / mart
                    │
                    ▼
              FastAPI 只读与受保护操作接口
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    分析查询     报告生成     运行与投递状态
        │           │           │
        ├───────────┴───────────┤
        ▼                       ▼
   Telegram 自动投递       微信文章包与公众号草稿
                                │
                                ▼
                          人工审核并发布
```

数据处理、报告生成和外部投递有独立失败边界。ETL 成功后，Telegram 或微信失败不会回滚数据库；不确定的外部请求不会被系统自动重复发送。

## 3. 分层设计

### 3.1 数据采集层

采集器负责取得经授权的快照或读取本地 JSON。当前公开仓库只提供快照适配和基础采集示例；高级浏览器采集器属于独立运行环境，不把浏览器 Profile、登录态或真实岗位数据纳入仓库。

主要目录：

```text
src/jobflow/adapters/
src/jobflow/collectors/
data/raw/
examples/
```

### 3.2 ETL 层

`src/jobflow/workers/` 负责单批次 ETL 编排：校验输入、创建批次、写入原始记录、标准化岗位、提交或回滚事务。适配器只负责来源格式转换，数据库写入规则集中在 Worker 和数据库模块中。

### 3.3 数据存储层

PostgreSQL 按职责分为四个 schema：

| Schema | 主要对象 | 职责 |
| --- | --- | --- |
| `ops` | 批次、运行检查、投递状态、微信草稿状态 | 运行与运维状态 |
| `raw` | 原始岗位记录 | 保留来源 payload |
| `core` | 标准岗位记录 | 标准化、去重和当前状态 |
| `mart` | 城市、薪资、技能视图 | 固定聚合查询 |

Migration 文件按编号演进。新增结构应使用新的 migration；当前 Compose 中的 migration 服务用于开发和自托管部署初始化，生产环境执行前应先核对已有数据库状态。

### 3.4 API 与报告层

主要目录：

```text
src/jobflow/api/
src/jobflow/db/
src/jobflow/reports/
src/jobflow/ai/
```

API 提供健康检查、就绪检查、城市/薪资/技能分析、报告生成、投递状态和受保护的人工操作接口。公共分析接口只执行固定白名单查询；AI 只接收结构化查询结果，不直接连接 PostgreSQL，也不能执行任意 SQL。

报告层支持：

- `query`：基于固定指标生成确定性查询简报，不需要 AI Key；
- `ai`：通过 OpenAI-compatible API 对固定结构化指标生成摘要；
- 趋势图和文章包：供 Telegram 图片消息和微信文章使用。

### 3.5 投递层

主要目录：

```text
src/jobflow/channels/
src/jobflow/operations/
```

#### Telegram

- 发送文字和 PNG 图表；
- 使用独立投递记录和状态；
- 网络错误发生在请求已到达服务端之后时，结果可能不确定；
- 不确定状态必须先人工核实，不自动重复发送。

#### 微信公众号

- 先生成 Markdown、HTML、封面、趋势图和 manifest 文章包；
- 上传封面和正文图片后创建待审核草稿；
- 草稿创建状态单独记录；
- 草稿失败不回滚 ETL 或 Telegram；
- 草稿创建成功后仍需后台人工审核和正式发布。

Telegram 与微信是两个独立渠道，可以单独检查、单独恢复，不能因为一条链路成功就推断另一条链路成功。

## 4. 部署架构

### 4.1 Docker Compose 服务

```text
compose.yaml
├─ postgres    常驻 PostgreSQL
├─ migrate     一次性 migration 工具
├─ etl         一次性快照导入工具
├─ api         常驻 FastAPI
├─ frontend    可选 React/Vite 操作界面
└─ dashboard   可选 Streamlit 运行界面
```

`compose.proxy.yaml` 可选增加 Mihomo 服务，为应用提供受控外联代理。Mihomo、订阅和节点属于部署环境能力，不属于业务核心；配置必须放在仓库外的私有运行目录。

### 4.2 Ubuntu 每日任务

```text
systemd timer
  → daily update service
  → ops/daily_update.sh
  → API 就绪检查
  → 快照检查/采集
  → ETL
  → Telegram 与微信文章阶段
  → 微信草稿创建
```

脚本负责顺序编排和失败退出，业务状态和幂等逻辑由 API、数据库及渠道服务负责。浏览器登录态失效时，任务应安全停止；恢复登录后再进行受控运行，不应盲目重复投递。

## 5. 关键数据流与失败边界

| 阶段 | 成功结果 | 失败处理 |
| --- | --- | --- |
| 快照校验 | 输入满足契约 | 停止 ETL，不写业务数据 |
| ETL | 批次、raw、core 成功提交 | 事务回滚，批次标记失败 |
| 报告生成 | 简报、趋势图或文章包生成 | 保留已提交 ETL，停止后续相关渠道 |
| Telegram | 文字和图片有明确状态 | 记录失败或不确定，人工核实后再恢复 |
| 微信草稿 | 草稿状态为已创建 | 不回滚 ETL/Telegram，先查状态和后台 |
| 正式发布 | 维护者完成后台审核发布 | 不由 OpenJobFlow 自动执行 |

## 6. 安全与隐私边界

- `.env`、API Key、Bot Token、Chat ID、Cookie、浏览器 Profile、私钥、真实快照和代理订阅只存在于部署者私有环境；
- 公开文档使用 `<SERVER_IP>`、`<JOBFLOW_DIR>` 等占位符；
- 数据库端口默认只绑定本机，API 是否开放到局域网由部署者自行配置；
- 报告触发接口使用独立鉴权凭据；
- 日志和错误响应不输出凭据、完整请求头或第三方服务敏感响应；
- 使用真实数据前必须确认数据来源授权、平台条款和隐私合规要求。

## 7. 当前实现状态

截至 2026-10-18：

- 分层 ETL、PostgreSQL 聚合视图、FastAPI 分析接口已实现；
- Telegram 图文投递链路已完成真实运行验证；
- 微信公众号文章包和待审核草稿链路已完成真实运行验证；
- Telegram 与微信状态独立记录，微信不自动正式发布；
- 每日脚本包含 API 就绪、采集、ETL 和投递失败边界；
- React/Vite 操作界面和 Streamlit 界面属于可选部署组件，仍按当前代码和部署环境分别验收；
- 当前公开基线为稳定性与可观测性维护状态，不代表高可用或长期无人值守稳定。

## 8. 后续工作

按优先级继续：

1. 完成 migration 增量执行和升级回滚策略；
2. 增加 PostgreSQL 备份、恢复演练、监控和告警；
3. 完善上游登录失效通知和人工恢复流程；
4. 补充连续多日运行、整机重启和异常投递的验收证据；
5. 在明确需求后再扩展抓取范围、分析页面或公网部署能力。

## 9. 相关文档

- [项目交接](project-handoff.md)：当前状态、新对话入口和下一步；
- [Ubuntu 部署与运行](guides/ubuntu-deployment.md)：自托管部署、定时任务和恢复边界；
- [微信公众号草稿](guides/wechat-official-draft.md)：文章包、草稿创建和排障；
- [数据源边界](reference/data-sources.md)：快照来源和合规边界；
- [历史设计与计划](archive/README.md)：已完成或被替代的材料。
