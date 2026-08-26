# 架构与实现状态

更新日期：2026-08-26

JobFlow 的主线是招聘数据 ETL 与只读分析。数据源、写入、查询、AI 总结和消息发送分别放在独立边界中，避免某一层的变化扩散到整个系统。

## 当前架构

```text
Ubuntu Chrome CDP / 本地快照 / 后续合规动态数据源
                    │
                    ▼
              Source Adapter
       读取 / 校验 / 薪资与技能标准化
                    │
                    ▼
                ETL Worker
        批次 / raw / core / 事务编排
                    │
                    ▼
                PostgreSQL
        ├─ ops：运行批次
        ├─ raw：来源原文
        ├─ core：标准岗位当前状态
        └─ mart：城市、薪资、技能聚合
                    │
                    ▼
             FastAPI 只读接口
           ┌────────┴────────┐
           ▼                 ▼
      分析接口          报告触发接口
                             │
                             ▼
        Query Report / Optional AI Summary Service
                             │
                             ▼
             报告与图表聚合层
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
   Telegram Bot 私聊      微信测试号模板
   文字 + PNG             聚合摘要
                              │
                              ▼
                   公众号文章排版包
                 Markdown / HTML / PNG
                              │
                              ▼
                   正式订阅号人工发布
```

每日 Shell 在 ETL 和文章包生成完成后并行触发 Telegram、微信两个渠道。渠道状态独立记录：同一渠道同一天只能成功认领一次，某个渠道失败不会阻止另一个渠道尝试。

网络受限的部署环境可以通过 `JOBFLOW_HTTP_PROXY`、`JOBFLOW_HTTPS_PROXY` 和 `JOBFLOW_NO_PROXY` 为应用容器提供外联代理。代理客户端、节点和订阅属于部署环境，不属于 JobFlow 业务架构，也不进入公开仓库。

## 模块边界

### Source Adapter

`src/jobflow/adapters/` 读取 BOSS JSON 快照，验证结构和必要字段，并把来源数据转换为统一 `JobRecord`。薪资文本解析和技能拆分在这一层完成，下游不重复理解来源格式。

### ETL Worker

`src/jobflow/workers/` 负责批次状态、raw/core 写入、提交、回滚和连接关闭。快照为空时正常结束；raw 或 core 写入失败时回滚业务写入，并把批次标为失败。

### PostgreSQL

当前已实现：

| Schema | 对象 | 职责 |
| --- | --- | --- |
| `ops` | `batches` | 保存 ETL 批次状态和行数 |
| `raw` | `job_records` | 保存来源原始 payload |
| `core` | `jobs` | 保存标准化、幂等去重后的岗位 |
| `mart` | 3 个 View | 提供城市岗位、城市月薪和技能聚合 |

当前 migration 位于 `migrations/001` 至 `009`，其中 `009` 预留微信公众号等新增渠道的独立投递状态表。mart 使用普通 PostgreSQL View，core 数据变化后查询结果自动更新，不需要 refresh。

### FastAPI

`src/jobflow/api/` 当前提供：

```http
GET  /health
GET  /ready
GET  /analytics/cities
GET  /analytics/salaries/cities
GET  /analytics/skills
POST /reports/cities/send
```

分析接口只执行固定 SQL，并将 `limit` 限制在 1 到 100。`/health` 检查 API 进程，`/ready` 执行 `SELECT 1` 检查数据库依赖。FastAPI 自动生成 `/docs` 和 `/openapi.json`。

### AI Summary Service 与 Telegram

`src/jobflow/reports/` 支持 `query` 与 `ai` 两种报告模式。`query` 使用数据库指标和固定规则生成中文查询简报；`ai` 才调用 `src/jobflow/ai/` 的 OpenAI-compatible Responses API。`src/jobflow/channels/` 通过 Telegram Bot API 发送文本和 PNG；企业微信适配器保留但未启用；微信公众号适配器只发送测试号模板摘要。渠道层不读取数据库、不生成报告，异常由上层状态机分类。

`POST /reports/cities/send` 使用 Bearer Token 保护。它查询最多 100 个城市，空数据时跳过发送；OpenAI 模型或 Telegram 失败时返回通用 `502/503`，不向客户端暴露秘密和内部异常。

当前状态：OpenAI 报告生成、Telegram 直发和完整报告接口均已进行功能验证；V1.1 每日脚本使用 `mode=query`，已通过 5 分钟 transient timer 真实完成 ETL 后 Telegram 私聊送达。AI 不直接连接数据库，Telegram 不参与 ETL 事务；发送失败不回滚数据库，但会让 daily service 失败。

## 部署架构

```text
Docker Compose
├─ postgres  常驻数据库
├─ migrate   一次性 migration 工具
├─ etl       一次性快照处理工具
├─ api       常驻 FastAPI
└─ mihomo    V1.2 可选服务器代理，仅 compose.proxy.yaml 启用
```

默认 `compose.yaml` 不包含代理服务。网络受限部署显式叠加 `compose.proxy.yaml` 后，API 使用内部服务名 `mihomo:7890`；Mihomo 不发布宿主机端口，订阅保存在 Git 忽略的运行目录或通过 `MIHOMO_CONFIG_DIR` 指向的仓库外私有目录。

宿主机 systemd 编排：

```text
jobflow-xvfb.service           长期虚拟显示
→ jobflow-boss-chrome.service  长期 Chrome/CDP 与人工登录态
→ jobflow-daily-update.timer   每天 09:00 Asia/Shanghai
→ jobflow-daily-update.service oneshot
→ ops/daily_update.sh          登录检查、抓取、原子快照、ETL、Telegram
```

ETL 与 API 复用同一个 Python 3.12 镜像，以不同命令启动。应用使用非 root 用户运行，快照目录只读挂载；PostgreSQL 只绑定宿主机 `127.0.0.1:5432`，API 通过 UFW 限制为局域网访问。

## 当前真实验收

截至 2026-08-17 在 Ubuntu 22.04.5 LTS 上完成：

```text
服务器：<SERVER_IP>
项目目录：<JOBFLOW_DIR>
Docker Engine：29
Docker Compose：v5.4.0
V1.1 快照：上海、北京、杭州、深圳各 15 条，合计 60 条
Adapter：60 条原始岗位全部标准化
systemd service：code=exited / status=0/SUCCESS
Telegram 报告：city_count=4，手机私聊真实收到
报告时数据库总量：397
城市分布：上海 124、北京 92、杭州 91、深圳 90
正式 timer：enabled / active (waiting) / 每天 09:00 CST
postgres：healthy
api：healthy
```

Ubuntu 本机与 Windows 局域网客户端均通过健康检查、就绪检查、三个分析接口和 `/docs` 验收。

2026-08-17 正式 09:00 timer 首次触发时，抓取与 ETL 成功，Telegram 因依赖的 Windows 代理关闭而失败。随后先用 Ubuntu 独立代理恢复发送，再把代理迁移为 V1.2 Compose 服务：API 为 `healthy`，Mihomo 为 `running`、`restart=unless-stopped`、无宿主机端口绑定，API 使用 `http://mihomo:7890`。迁移后 Telegram `getMe` 返回 200，真实 `mode=query` 报告送达手机，Mihomo 重启后 `getMe` 仍成功。

2026-08-18 用户进一步确认：Windows 本地机关闭后，Ubuntu 已通过服务器 Compose Mihomo 完成正式定时推送并送达 Telegram。这证明定时运行链路不依赖 Windows；连续多日和整机重启恢复仍保持未验收状态。

2026-08-19 V1.3 在 Ubuntu 完成一次真实完整链路：Chrome 151 通过前台 CDP Target 执行登录探测、Network 域被动捕获和列表抓取；上海、北京、杭州、深圳各抓取 3 页、45 条，共合并 180 条；随后 ETL 完成、每日不可变快照和对比简报生成，Telegram 收到中文文字与 Matplotlib 城市构成 PNG，脚本退出码为 0。详情抓取仍保持后台 Target；采集器修复在服务器上是基于 `2bc40f5` 的未提交补丁，本机修复提交 `7020397` 已创建上游 PR `#68`，但尚未合并。

城市构成图的分母是本轮固定页数抓取样本，而不是全站岗位总体。当四个城市都抓满相同页数时，图中 25% 只表示本次抽样数量相同。

## 当前未完成

- 整机重启和连续多日运行；
- Chrome/BOSS 登录失效自动通知；
- 后续版本的多关键词和更大抓取范围；
- API 独立只读数据库角色；
- 公网域名、Caddy、HTTPS、完整鉴权和限流；
- PostgreSQL 自动备份、恢复演练、监控和告警；
- 合规动态数据源替换或授权边界完善；
- Streamlit 分析页面。

## 架构原则

- Adapter 隔离数据源变化；
- Worker 是数据库写入边界；
- API 只读取白名单聚合指标；
- AI 只总结结构化结果，不生成无数据依据的事实；
- 消息渠道只负责发送；
- 密钥和真实数据不进入 Git、镜像、日志或文档；
- 局域网部署完成不等于公网生产上线。

启动和继续开发时先阅读 [`project-handoff.md`](project-handoff.md)。
