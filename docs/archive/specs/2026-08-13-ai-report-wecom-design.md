# AI 城市报告与企业微信发送设计

日期：2026-08-13

状态：设计已确认，等待实施计划

## 1. 目标

在 JobFlow 现有城市岗位统计 API 基础上，增加一条可部署到个人 Ubuntu 服务器的 AI 报告发送链路：读取 `mart.city_job_counts` 聚合数据，使用 OpenAI Responses API 生成中文报告，并通过企业微信群机器人 Webhook 发送。

第一版只支持城市岗位数量报告和一个企业微信群机器人，不扩展薪资、技能、多个渠道或定时调度。

## 2. 接口与鉴权

新增接口：

```http
POST /reports/cities/send
Authorization: Bearer <REPORT_TRIGGER_TOKEN>
```

服务端从 `REPORT_TRIGGER_TOKEN` 读取预共享令牌。缺少令牌或令牌不匹配时返回 HTTP `401`，且不得查询数据库、调用 OpenAI 或发送企业微信。

成功响应：

```json
{
  "status": "sent",
  "city_count": 10
}
```

## 3. 数据流

```text
POST /reports/cities/send
        ↓
Bearer Token 鉴权
        ↓
读取 mart.city_job_counts
        ↓
生成结构化城市统计
        ↓
OpenAI Responses API
        ↓
生成中文招聘分析报告
        ↓
企业微信群机器人 Webhook
        ↓
返回发送结果
```

## 4. 模块边界

```text
src/jobflow/db/analytics.py
→ 读取城市聚合数据

src/jobflow/ai/openai_summary.py
→ 调用 OpenAI 并返回文本

src/jobflow/channels/wecom.py
→ 调用企业微信 Webhook

src/jobflow/reports/service.py
→ 编排查询、总结和发送

src/jobflow/api/reports.py
→ Bearer Token 鉴权和 HTTP 响应
```

OpenAI、企业微信和 API 路由不直接连接 `raw`，不执行数据库写操作，也不改变 ETL Worker 的事务边界。

## 5. OpenAI 调用

使用 OpenAI 官方 Python SDK 和 Responses API：

```python
response = client.responses.create(...)
report = response.output_text
```

模型从 `OPENAI_MODEL` 读取，不写死在业务代码中。API Key 使用 SDK 默认支持的 `OPENAI_API_KEY` 环境变量。

模型输入只包含城市名称、岗位数量和指标口径。提示词必须要求：

- 只基于输入数据陈述事实。
- 不编造薪资、趋势、技能或原因。
- 明确统计口径是当前数据库中的岗位数量。
- 输出适合企业微信群阅读的简洁中文报告。

## 6. 企业微信发送

Webhook 从 `WECOM_WEBHOOK_URL` 读取。第一版发送企业微信机器人 `text` 消息，并检查 HTTP 状态码以及响应 JSON 中的 `errcode`。

任何日志和错误响应都不得包含完整 Webhook URL。

## 7. 空数据与错误处理

- 无城市数据：不调用 OpenAI，也不发送企业微信；接口返回 HTTP `200` 和 `{"status": "skipped", "city_count": 0}`。
- 配置缺失：返回 HTTP `503`，错误信息只指出缺少哪类服务配置，不显示密钥值。
- PostgreSQL 或 OpenAI 失败：返回 HTTP `503`，且不发送企业微信。
- 企业微信网络失败或 `errcode != 0`：返回 HTTP `502`。
- 成功发送：返回 HTTP `200` 和 `{"status": "sent", "city_count": <实际城市数>}`。

## 8. 环境变量

Ubuntu 运行环境必须配置：

```text
OPENAI_API_KEY
OPENAI_MODEL
WECOM_WEBHOOK_URL
REPORT_TRIGGER_TOKEN
```

`.env.example` 只记录变量名和非敏感示例，不包含真实 API Key、Webhook Key 或触发令牌。

## 9. 测试与真实验收

自动化测试必须覆盖：

- 鉴权失败不会调用报告服务。
- 城市数据正确进入 OpenAI 输入。
- 空数据跳过 OpenAI 和企业微信。
- OpenAI 失败不会发送企业微信。
- 企业微信请求格式正确。
- 企业微信失败映射为 HTTP `502`。
- 完整成功链路返回 `sent`。

自动化测试使用 Mock，不真实消耗 OpenAI 额度或发送群消息。最后使用专用测试群进行一次真实人工验收，并只记录成功或失败结果，不记录密钥。

## 10. 明确不做

- 普通个人微信自动化。
- 多机器人平台适配。
- 网页用户和复杂权限系统。
- 消息队列、APScheduler 或任务锁。
- 薪资、技能和趋势报告。
- 保存完整 AI 对话。
- 机器人直接访问 PostgreSQL。

## 11. 完成标准

- 带正确 Bearer Token 的请求能生成并发送城市岗位报告。
- 错误令牌不能触发任何外部调用。
- 报告只使用允许的聚合事实。
- OpenAI 与企业微信失败得到安全、明确的 HTTP 响应。
- 密钥不进入 Git、日志或 API 响应。
- 自动化测试、Ruff、格式和 Git 差异检查通过。
