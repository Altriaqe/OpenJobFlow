# JobFlow V1.1 每日 Telegram 报告发送设计

## 1. 背景与目标

JobFlow 当前已经在 Ubuntu 上完成以下真实链路：

```text
Chrome CDP 四城市抓取
→ JSON 合并与原子替换
→ JobFlow ETL
→ PostgreSQL
→ FastAPI 查询报告接口
→ Telegram 私聊
```

`jobflow-daily-update.timer` 已设置为每天 `09:00 Asia/Shanghai` 触发，Xvfb 和 Chrome 作为 systemd 服务长期运行，`jobflow-daily-update.service` 已手动完成一次四城市抓取和 ETL。

当前缺口是：每日脚本在 ETL 成功后尚未调用现有报告接口，因此 timer 明天只会更新数据库，不会自动发送 Telegram 消息。

本设计目标：

```text
每日 timer
→ 抓取与 ETL
→ 固定规则中文报告
→ Telegram 私聊真实送达
```

当前没有浏览器可视化页面，Telegram 是 V1.1 的主要结果展示出口。

## 2. 范围

### 2.1 本次包含

- 在 `ops/daily_update.sh` 的 ETL 成功分支末尾调用现有报告接口；
- 固定使用 `mode=query`；
- 复用 API 容器已有的 `REPORT_TRIGGER_TOKEN`；
- 只有报告接口返回 `status=sent` 才判定 Telegram 阶段成功；
- Telegram 阶段失败时，让 systemd daily service 以失败状态结束；
- 保留已经成功提交的 ETL 数据，不回滚数据库；
- 使用当前时间后 5 分钟的临时 transient timer 做真实端到端验收；
- 测试后确认正式每天 09:00 timer 未被修改。

### 2.2 本次不包含

- 不调用 OpenAI 兼容服务/OpenAI；
- 不使用 `mode=ai`；
- 不开发浏览器 Dashboard、Streamlit 或其他视图界面；
- 不开发 Telegram 入站“今日总结”指令；
- 不把账号密码、Bot Token、Chat ID 或触发 Token 写入脚本；
- 不自动绕过验证码或登录验证；
- 不实现 Telegram 独立重试队列；
- 不回滚已经成功的 ETL；
- 不修改正式 timer 的 09:00 计划来完成测试。

## 3. 已有能力复用

现有接口：

```http
POST /reports/cities/send?mode=query
Authorization: Bearer <REPORT_TRIGGER_TOKEN>
```

现有业务调用：

```text
FastAPI 鉴权
→ 查询 mart.city_job_counts
→ build_query_report(rows)
→ send_telegram_text(report)
→ Telegram Bot sendMessage
```

成功返回：

```json
{"status":"sent","city_count":4}
```

没有城市数据时可能返回：

```json
{"status":"skipped","city_count":0}
```

当前报告服务和 Telegram 发送器已有离线测试，并已经在 Ubuntu 上完成真实私聊发送验收。本次不重写报告生成、鉴权或 Telegram 适配器。

## 4. 方案选择

### 4.1 选定方案：调用现有 HTTP 报告接口

```text
daily_update.sh
→ ETL completed
→ 在 API 容器内调用本机报告接口
→ API 使用容器环境变量鉴权
→ Telegram 发送
```

选择原因：

- 与人工调用报告时走同一条正式业务路径；
- 复用已经验证的鉴权、查询、报告模板和 Telegram 错误映射；
- 不产生第二套数据库连接和报告调用方式；
- 容易通过 HTTP 状态码和 JSON `status` 验收。

### 4.2 未选方案

直接从脚本导入 Python 报告服务：会重复处理数据库连接、容器环境和配置边界。

单独创建 Telegram systemd service：解耦更强，但增加 service 编排、状态和重试复杂度，超出当前 V1.1 所需范围。

## 5. 安全调用方式

报告请求在已经运行的 `api` 容器内部发起。调用程序从容器环境读取 `REPORT_TRIGGER_TOKEN`，而不是从宿主机 `.env` 展开到 curl 命令参数。

安全要求：

- 脚本只出现变量名 `REPORT_TRIGGER_TOKEN`，不出现实际值；
- 不执行 `set -x`；
- 不把请求 Authorization 头打印到 journal；
- 不在 systemd unit 中写 Token；
- 不把 `.env`、Chrome Profile 或 Telegram 配置提交 Git；
- HTTP 请求目标使用 API 容器内部的 `http://127.0.0.1:8000`；
- 对外日志只记录发送成功、HTTP 状态和通用失败原因。

API 容器未运行或环境变量缺失时，Telegram 阶段失败并让 daily service 失败。

## 6. 最终数据流

```text
jobflow-daily-update.timer
→ jobflow-daily-update.service
→ ops/daily_update.sh
→ flock 单实例锁
→ boss_cdp_raw.py --check
→ 上海 / 北京 / 杭州 / 深圳抓取
→ 临时目录
→ {"jobs": [...]} 合并
→ os.replace 原子快照
→ docker compose run --rm etl
→ ETL 成功提交
→ API 容器内 POST /reports/cities/send?mode=query
→ 固定规则中文简报
→ Telegram Bot 私聊
→ status=sent
→ daily service 成功
```

## 7. 失败与事务边界

### 7.1 Telegram 之前失败

以下任一环节失败时立即停止：

- 任务锁被占用；
- Chrome/CDP/BOSS 登录检查失败；
- 任一城市抓取失败；
- JSON 合并或结构校验失败；
- ETL 失败。

这些失败不会调用报告接口。

### 7.2 ETL 成功、Telegram 失败

采用已批准的规则 A：

```text
ETL 成功并提交数据库
→ Telegram 调用失败
→ 不回滚数据库
→ daily_update.sh 非零退出
→ systemd service 标记 failed
→ journal 保留失败证据
```

原因：数据库更新与外部消息发送不属于同一个事务。不能因为网络或 Telegram 故障删除已成功入库的数据，但也不能把“没有收到报告”标记为整次任务成功。

### 7.3 `status=skipped`

`status=skipped` 表示未发送 Telegram 消息。即使 HTTP 请求本身成功，也不满足本次业务目标，因此 daily service 应失败。

### 7.4 任务锁被占用

现有脚本在锁被占用时以 `exit 0` 安全跳过。它表示本次没有获得执行资格，不是一次已经开始的 Telegram 发送尝试；“只有 `status=sent` 才成功”的规则从获取任务锁并进入正式更新流程后开始适用。测试 timer 不应与正式任务或人工运行重叠；测试前需确认 daily service 未运行。

## 8. 五分钟端到端测试

### 8.1 测试方式

不修改 `/etc/systemd/system/jobflow-daily-update.timer`。使用 `systemd-run` 创建临时 transient timer，在当前时间后 5 分钟触发同一个 `jobflow-daily-update.service`。

```text
临时 timer
→ 5 分钟倒计时
→ systemctl start jobflow-daily-update.service
→ 完整抓取、ETL、Telegram
```

### 8.2 测试前置条件

- `jobflow-xvfb.service` 为 `active`；
- `jobflow-boss-chrome.service` 为 `active`；
- BOSS `--check` 显示已登录；
- PostgreSQL 和 API 容器为 `healthy`；
- 正式 timer 仍为 `active (waiting)`；
- 当前没有 daily service 正在运行；
- Telegram 私聊配置已经真实验收。

### 8.3 验收标准

必须同时满足：

1. 临时 timer 在约 5 分钟后触发；
2. journal 显示登录预检查通过；
3. 四城市抓取和合并成功；
4. ETL 输出 `ETL completed`；
5. 报告阶段输出成功，并确认响应 `status=sent`；
6. 用户手机 Telegram 私聊真实收到本次中文报告；
7. `jobflow-daily-update.service` 本次结果为成功；
8. 正式 timer 的下一次触发仍为每天 09:00；
9. 临时 timer 完成后被清理或不再计划下一次运行；
10. 日志没有泄露 Token、Cookie、密码或 `.env` 实际值。

### 8.4 失败验收

如果手机没有收到报告：

- 不重复盲目触发完整抓取；
- 先查看 daily service journal；
- 再区分 API 不可用、鉴权失败、Telegram 配置错误和 Telegram 网络失败；
- 确认最新 ETL 批次是否已经 `succeeded`；
- 根据失败层级决定只补发报告还是重新运行完整任务。

## 9. 正式运行状态

五分钟测试通过后，正式 timer 保持：

```text
OnCalendar=*-*-* 09:00:00 Asia/Shanghai
Persistent=true
Unit=jobflow-daily-update.service
```

Windows 本机关机、TigerVNC 关闭、SSH 隧道关闭都不影响 Ubuntu 定时任务。Ubuntu 服务器必须保持开机和联网；Xvfb、Chrome、PostgreSQL、API 和 BOSS 登录态必须可用。

当前准确表述：

```text
五分钟测试前：自动 Telegram 发送设计已批准，尚未接入脚本
五分钟测试通过后：完整自动链路单次真实验收通过
连续运行后：才能表述为每日自动发送已连续稳定运行
```

## 10. 文档与提交边界

- 更新根 README 的维护、自动发送和故障恢复说明；
- 更新 Ubuntu 部署文档和正式项目交接；
- 更新 Obsidian systemd、Telegram、V1.1 和 Day 22 笔记；
- 不创建 Day 23；
- 不提交 `.env`、真实快照、Profile 或 systemd 服务器本地敏感文件；
- 任何 commit 或 push 必须获得用户明确授权。
