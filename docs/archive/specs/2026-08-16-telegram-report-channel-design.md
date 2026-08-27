# Telegram 报告通知渠道设计

日期：2026-08-16
状态：设计已获用户确认，待实施计划
范围：保留报告触发接口，将默认消息渠道从企业微信机器人改为 Telegram 私聊

## 1. 目标与边界

保留现有 `POST /reports/cities/send` 接口、Bearer Token 保护、城市岗位查询和 OpenAI 兼容服务 OpenAI 兼容接口报告生成能力。新增 Telegram Bot API 发送适配器，把生成的中文城市岗位报告发送到用户自己的 Telegram 私聊。

本次不实现普通个人微信自动化，不模拟桌面登录或控制个人微信客户端；企业微信适配器暂时保留，但不再作为默认发送器。

## 2. 数据流与模块边界

```text
POST /reports/cities/send
    -> Bearer Token 校验
    -> 查询 mart.city_job_counts（最多 100 个城市）
    -> OpenAI 兼容服务 OpenAI 兼容接口生成事实约束报告
    -> Telegram Bot API sendMessage
    -> 返回 status=sent 和 city_count
```

模块职责：

- `src/jobflow/reports/service.py`：继续编排查询、总结和发送，不理解 Telegram 协议细节。
- `src/jobflow/channels/telegram.py`：新增 Telegram 发送适配器，读取配置、构造 `sendMessage` 请求并验证响应。
- `src/jobflow/api/reports.py`：保留路径和认证；将 Telegram 配置错误映射为通用 `503`，发送失败映射为通用 `502`。
- `src/jobflow/channels/wecom.py`：暂时保留，作为未启用的旧渠道，不作为默认发送器。

Telegram 请求使用 HTTPS：

```text
POST https://api.telegram.org/bot<TOKEN>/sendMessage
{
  "chat_id": "<私聊 Chat ID>",
  "text": "<报告内容>"
}
```

## 3. 配置与安全

服务器 `.env` 新增：

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

继续使用：

```text
REPORT_TRIGGER_TOKEN
OPENAI_BASE_URL
OPENAI_API_KEY
OPENAI_MODEL
```

配置要求：

- `.env` 权限保持 `600`。
- Bot Token、Chat ID、报告触发 Token 不进入 Git、镜像、日志、截图、异常文本或 API 响应。
- Telegram API 固定使用 HTTPS。
- Docker 容器运行时必须继承服务器可用的 HTTP/HTTPS 代理；代理属于部署运行配置，不写入 Python 源码。

## 4. 错误处理

- 缺少 `TELEGRAM_BOT_TOKEN` 或 `TELEGRAM_CHAT_ID`：抛出配置错误，API 返回通用 `503`。
- Telegram 网络错误、HTTP 错误或 JSON 响应 `ok=false`：抛出发送错误，API 返回通用 `502`。
- OpenAI/OpenAI 兼容服务 失败：保持现有通用 `503` 边界。
- 查询结果为空：返回 `skipped`，不调用 AI，也不发送 Telegram。
- 报告超过 Telegram 单条消息限制时，发送适配器报错，不截断或静默丢失报告。

客户端不接收 Token、Chat ID、Webhook 或第三方原始异常。

## 5. 测试与真实验收

单元测试覆盖：

- Telegram 请求 URL、JSON 载荷和超时参数；
- 缺少配置；
- 网络/HTTP 异常；
- Telegram 返回 `ok=false`；
- 空数据不触发 AI 或发送器；
- API Bearer Token、成功响应和错误映射。

真实 Ubuntu 验收顺序：

1. 在服务器 `.env` 配置 Telegram Bot Token 和私聊 Chat ID，不显示实际值。
2. 确认 Docker 运行容器继承代理。
3. 重建包含新渠道代码的应用镜像。
4. 单独发送一条测试文本，确认 Telegram 私聊收到。
5. 带 `Authorization: Bearer <REPORT_TRIGGER_TOKEN>` 调用 `POST /reports/cities/send`。
6. 确认 Telegram 私聊收到由当前数据库城市岗位数据生成的报告。

只有第 4、6 步都成功，才能称为 Telegram 真实联调完成；代码存在、离线测试通过或 HTTP 200 本身都不等于消息已送达。

## 6. 非目标

- 不实现普通个人微信群机器人。
- 不实现企业微信重新开通或账号升级。
- 不新增定时任务、重试队列、消息持久化或多渠道选择配置。
- 不改变 ETL、PostgreSQL schema、分析接口和报告触发路径。
