# JobFlow Ubuntu 容器化部署设计

**日期：** 2026-08-14

**状态：** 已完成方案确认，待实施

**范围：** Docker 镜像、Compose 服务、手动 ETL、FastAPI 健康检查与局域网访问

## 一、目标

把现有 JobFlow 数据链路部署到 Ubuntu 22.04，使服务器能够：

- 使用 Docker Compose 运行 PostgreSQL；
- 手动处理 Windows 上传的 BOSS JSON 快照；
- 将原始数据和标准化岗位写入 PostgreSQL；
- 持续运行 FastAPI，向局域网提供城市、薪资和技能分析接口；
- 为以后通过域名、Caddy 和 HTTPS 上线预留结构。

本阶段先完成稳定的数据底座，不部署尚未稳定的 OpenAI 报告和企业微信发送模块。

## 二、已确认的部署边界

- Ubuntu 主机按需开机，不要求 24 小时运行；
- 第一版只允许局域网 `<LAN_CIDR>` 访问 FastAPI；
- PostgreSQL 不向局域网或公网开放；
- ETL 在上传新快照后由用户手动触发，不随服务器或 API 自动启动；
- API 作为长期运行服务，由 Docker Compose 管理；
- `.env`、原始快照、密码、Token 和 Webhook 不进入 Git 或 Docker 镜像；
- 未来域名上线属于后续阶段，本阶段不配置公网映射、DNS 或 HTTPS。

## 三、方案选择

采用一个 Dockerfile 构建统一 JobFlow 镜像，Compose 中的 `etl` 和 `api` 服务复用该镜像，仅使用不同启动命令。

未选择的方案：

- API 和 ETL 分别维护 Dockerfile：隔离更强，但依赖和构建逻辑重复；
- PostgreSQL 容器化、Python 直接安装到 Ubuntu：初期命令少，但会污染主机环境并增加版本漂移；
- API 启动时自动执行 ETL：可能在重启时重复处理快照；
- 定时扫描快照目录：第一版暂时没有持续调度需求。

统一镜像能够保证 ETL 与 API 使用相同的 Python 3.12、JobFlow 代码和依赖，也便于以后升级和回滚。

## 四、容器架构

```text
Docker Compose
├── postgres  PostgreSQL 18，保存 ops/raw/core/mart
├── migrate   一次性执行 migrations/001～005
├── etl       一次性处理指定 JSON 快照
└── api       持续运行 FastAPI
```

服务职责：

| 服务 | 生命周期 | 职责 |
| --- | --- | --- |
| `postgres` | 长期运行 | 保存批次、原始记录、标准岗位和分析 View |
| `migrate` | 手动一次性运行 | 按文件名顺序应用 SQL migration，任一失败立即停止 |
| `etl` | 手动一次性运行 | 校验、映射并写入一份指定快照，完成后退出 |
| `api` | 长期运行 | 提供健康检查和只读分析接口 |

`etl` 和 `api` 通过 Compose 内部网络使用服务名 `postgres` 连接数据库。PostgreSQL 的宿主机端口继续绑定 `127.0.0.1`。

## 五、镜像与运行时

新增单个 `Dockerfile`：

- 基于 Python 3.12 slim 镜像；
- 安装 `pyproject.toml` 声明的生产依赖和 JobFlow 包；
- 不安装测试、Ruff 等开发依赖；
- 使用非 root 用户运行应用；
- 不把 `.env`、`.git`、缓存、测试输出或 `data/raw` 复制进镜像。

新增 `.dockerignore` 固定构建上下文边界。快照由只读 volume 挂载给 ETL，而不是打包进镜像。

## 六、ETL 命令入口

新增明确的命令行入口，接收一个快照路径并调用现有 `run_boss_snapshot()`。Compose 中的使用形式为：

```bash
docker-compose -f compose.yaml run --rm etl \
  /data/raw/inbox/boss_jobs.json
```

入口职责仅包括：

- 解析快照路径；
- 调用现有 ETL Worker；
- 成功时打印文件路径和处理完成信息并返回退出码 `0`；
- 失败时向标准错误输出安全、可定位的信息并返回非零退出码。

字段校验、标准化、数据库事务和批次状态继续由现有 Adapter 与 Worker 负责，命令行层不重复实现业务逻辑。

## 七、数据流与重复处理

```text
Windows BOSS 快照
        |
        | SCP
        v
data/raw/inbox/boss_jobs.json
        |
        | 手动 ETL
        v
字段校验、薪资解析、技能拆分、城市提取
        |
        +------> raw.job_records  原始批次历史
        |
        +------> core.jobs        标准岗位当前状态
                         |
                         v
               mart 三个分析 View
                         |
                         v
                    FastAPI
```

重复执行同一快照时：

- `raw.job_records` 以新批次保存再次处理的原始历史；
- `core.jobs` 按 `(source, external_id)` Upsert，不产生重复业务岗位；
- 内容变化时更新岗位内容和 `updated_at`，未变化时更新 `last_seen_at`；
- mart 使用普通 PostgreSQL View，自动读取最新 core 数据，不需要刷新命令。

## 八、事务与错误处理

- 快照不存在、JSON 非法、字段缺失或薪资格式无法解析时，ETL 停止；
- 批次开始后，raw/core 任一步写入失败时回滚该批次的数据写入；
- `ops.batches` 将失败批次标记为 `failed` 并保存错误原因；
- 成功批次标记为 `succeeded` 并记录处理行数；
- migration 使用 `ON_ERROR_STOP=1`，第一条 SQL 错误立即终止；
- API 不把数据库连接参数、SQL、密码或 traceback 返回给调用方；
- 日志不输出 `.env`、OpenAI Key、企业微信 Webhook 等秘密。

## 九、API 健康检查

保留已有只读分析接口：

- `GET /analytics/cities`；
- `GET /analytics/salaries/cities`；
- `GET /analytics/skills`。

新增：

| 接口 | 含义 | 成功条件 |
| --- | --- | --- |
| `GET /health` | 进程存活检查 | FastAPI 能处理请求，返回 `200` |
| `GET /ready` | 服务就绪检查 | 能执行最小 PostgreSQL 查询，返回 `200` |

数据库不可用时，`/health` 仍可返回 `200`，`/ready` 返回 `503`。这样可以区分“API 进程退出”和“API 存活但数据库不可用”。

## 十、网络与未来域名

当前阶段：

```text
Windows/局域网设备 -> Ubuntu:8000 -> FastAPI -> PostgreSQL
```

- FastAPI 容器监听 `0.0.0.0:8000`；
- Ubuntu UFW 只允许 `<LAN_CIDR>` 访问宿主机 `8000/tcp`；
- PostgreSQL 宿主机映射保持 `127.0.0.1:5432`；
- 不在路由器配置公网端口转发。

后续域名上线：

```text
域名 -> HTTPS/Caddy -> FastAPI -> PostgreSQL
```

届时新增 Caddy、DNS、TLS、鉴权和公网防火墙策略。域名不会直接连接 FastAPI 或 PostgreSQL，数据库业务代码无需重写。

## 十一、测试与验收

代码验收：

1. 命令行入口测试覆盖成功、参数错误和 ETL 异常；
2. `/health` 测试验证不依赖数据库；
3. `/ready` 测试验证数据库成功和失败分支；
4. Compose 配置能够解析；
5. Docker 镜像能够成功构建；
6. 原有全量测试和 Ruff 检查继续通过。

Ubuntu 验收：

1. `postgres` 状态为 healthy；
2. migrations 可按顺序执行，重复执行不破坏现有结构；
3. ETL 成功处理已上传的 30 条 BOSS 岗位；
4. `ops.batches` 最新批次为 `succeeded` 且 `row_count = 30`；
5. 该批次在 `raw.job_records` 中有 30 条记录；
6. `core.jobs` 中有 30 条当前岗位；
7. 三个 mart View 均能查询；
8. Ubuntu 本机访问 `/health`、`/ready` 和三个分析接口成功；
9. Windows 通过 `http://<SERVER_IP>:8000` 访问上述接口成功；
10. 局域网外没有开放 PostgreSQL 或 FastAPI 公网入口。

## 十二、不在本阶段处理的内容

- OpenAI 报告生成；
- 企业微信群机器人发送；
- 定时采集、定时 ETL 或目录自动扫描；
- 公网端口映射、域名解析、Caddy 和 HTTPS；
- 用户账号、API Key 鉴权和访问限流；
- PostgreSQL 备份与异机恢复自动化；
- 监控、告警和集中日志平台。

这些能力在数据链路和局域网部署验收后分阶段增加。
