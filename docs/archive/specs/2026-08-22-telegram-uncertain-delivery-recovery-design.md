# Telegram 超时防重复与只补图恢复设计

## 1. 背景与问题

2026-08-22，JobFlow V1.3.1 的四关键词抓取和 ETL 全部成功，但 Telegram 图文投递失败。用户实际收到了 3 条内容相同的文字简报，未收到热力图。

服务器证据：

```text
四个关键词抓取和 ETL：completed
报告接口：TimeoutError
四份 ops.report_deliveries：status=failed
text_message_id=NULL
photo_message_id=NULL
text_attempts=3
photo_attempts=0
last_error_type=telegram_delivery
```

根因是 Telegram 请求存在“结果不确定”窗口：Telegram 可能已接收并投递消息，但 HTTP 响应在返回 JobFlow 前超时或中断。当前代码把该情况当作“未发送”并自动重试 3 次，造成重复文字；文字阶段最终抛错后，图片阶段没有执行。

Telegram Bot API 不提供客户端幂等键，因此无法在所有网络故障下实现严格的“恰好一次”。本设计的原则是：结果不确定时停止自动重试，优先避免重复刷屏。

## 2. 目标

1. Telegram 文字或图片超时时，单次任务最多调用对应 Telegram 方法 1 次。
2. 数据库区分“明确失败”和“结果不确定”。
3. 结果不确定后，定时任务和普通发送接口不自动重发相同阶段。
4. 用户明确确认“文字已在 Telegram 可见”后，可只补发当日图片。
5. 请求并发到达时，只有一个请求能进入外部发送阶段。
6. 2026-08-22 的恢复不重新抓取、不重新 ETL、不再发文字，只补一张正式热力图。

## 3. 非目标

- 不引入 Redis、Celery、Kafka 或独立消息队列。
- 不尝试伪造、猜测或从 Telegram 界面推导丢失的文字 `message_id`。
- 不自动删除已经送达的重复消息。
- 不改变关键词、城市、页数、快照或趋势计算口径。
- 不声称 Telegram 外部投递可以实现数学意义的绝对恰好一次。

## 4. 方案比较与选择

### 方案 A：结果不确定状态 + 单次请求 + 人工恢复（采用）

优点：防止网络响应丢失时自动刷屏；数据库保留真实的不确定性；能只恢复未完成的图片阶段。

代价：不确定状态需要人工查看 Telegram 后恢复。

### 方案 B：只延长超时

优点：改动小。

缺点：只降低问题概率，不消除响应丢失后的重复发送。

### 方案 C：队列 + Outbox Worker

优点：内部任务调度更完整。

缺点：引入过重，而且 Telegram 仍没有幂等键，不能消除外部请求的不确定窗口。

## 5. 投递状态机

`ops.report_deliveries.status` 扩展为：

```text
pending
text_sending
text_sent
text_failed
text_uncertain
photo_sending
photo_failed
photo_uncertain
completed
completed_text_uncertain
failed                # 旧版兼容，禁止自动重发
partial_failed        # 旧版兼容，禁止自动重发
```

字段约束：

| 状态 | text_message_id | photo_message_id | 含义 |
| --- | --- | --- | --- |
| `pending` | NULL | NULL | 未发送 |
| `text_sending` | NULL | NULL | 一个请求已取得文字发送权 |
| `text_sent` | 正整数 | NULL | 文字明确成功 |
| `text_failed` | NULL | NULL | Telegram 明确拒绝，不自动重试 |
| `text_uncertain` | NULL | NULL | 超时或连接中断，不知是否送达 |
| `photo_sending` | 正整数或 NULL | NULL | 一个请求已取得图片发送权 |
| `photo_failed` | 正整数或 NULL | NULL | 图片被明确拒绝 |
| `photo_uncertain` | 正整数或 NULL | NULL | 图片结果不确定 |
| `completed` | 正整数 | 正整数 | 图文回执都明确 |
| `completed_text_uncertain` | NULL | 正整数 | 用户确认文字可见，图片回执明确 |
| `failed` | NULL | NULL | 旧版文字失败状态，只作兼容输入 |
| `partial_failed` | 正整数 | NULL | 旧版图片失败状态，只作兼容输入 |

不再将 `failed` 当作 `pending`。旧状态保留为迁移兼容输入，但新代码在没有人工确认时不会从旧 `failed` 自动重发。

## 6. 正常发送流程

1. 加载当天四份快照和投递记录。
2. 校验四份采集范围一致。
3. 锁定四份投递记录，确认都为 `pending`。
4. 在调用 Telegram 之前，将四份记录改为 `text_sending` 并提交。
5. Telegram 文字只请求 1 次：
   - 成功：四份记录保存同一 `text_message_id`，状态为 `text_sent`。
   - 明确 HTTP 拒绝：记为 `text_failed`。
   - 超时、连接中断或无法判定的客户端错误：记为 `text_uncertain`。
6. 只有文字明确成功时自动进入图片阶段。
7. 发图前将四份记录改为 `photo_sending` 并提交。
8. Telegram 图片只请求 1 次：
   - 成功：保存同一 `photo_message_id`，状态为 `completed`。
   - 明确拒绝：`photo_failed`。
   - 超时或断线：`photo_uncertain`。

## 7. 并发保护

在 PostgreSQL 事务内使用 `SELECT ... FOR UPDATE` 锁定当天四份 `ops.report_deliveries`。发送请求在持有数据库行锁时只执行状态预占，不在长时间网络请求期间持有行锁。

预占流程：

```text
FOR UPDATE 锁定四行
→ 再次检查状态
→ 写入 text_sending 或 photo_sending
→ commit 释放行锁
→ 调用 Telegram
```

后到的请求看到 `*_sending`、`*_uncertain`、`*_failed` 或完成状态时立即停止，不调用 Telegram。

`flock` 继续保护 `ops/daily_update.sh` 整体不并发；数据库状态预占保护 API 被手工或其他客户端重复调用。

## 8. 人工只补图接口

新增：

```http
POST /reports/daily/multi/recover-photo
  ?snapshot_date=YYYY-MM-DD
  &confirm_text_visible=true
Authorization: Bearer <REPORT_TRIGGER_TOKEN>
```

约束：

1. 必须通过现有 Bearer Token 验证。
2. `confirm_text_visible` 必须显式为 `true`；缺失或为 `false` 时返回 409，不调用 Telegram。
3. 四份快照必须齐全且采集范围一致。
4. 四份投递记录必须处于同一阶段；允许的输入为 `text_uncertain`、具有 Telegram 发送失败证据的旧 `failed`，或已保存文字 message ID 的旧 `partial_failed`。
5. 接口先将四份记录转为 `photo_sending` 并提交，再渲染和发送当日热力图。
6. 接口不调用文字发送器。
7. 对 `text_uncertain` 或旧 `failed` 的恢复，图片成功时状态为
   `completed_text_uncertain`；对已有明确文字 message ID 的旧
   `partial_failed`，图片成功时状态为 `completed`。图片超时时均为
   `photo_uncertain`。
8. `photo_uncertain` 不能直接再调用同一接口。用户必须先确认 Telegram 中确实没有图片，后续才能执行单独、显式的人工重置流程；该重置不在本次最小实现范围内。

## 9. Telegram 异常分类

新增 `TelegramDeliveryUncertain`，与已有 `TelegramDeliveryError` 区分：

- `TelegramDeliveryUncertain`：超时、连接中断、HTTP 5xx，或在已发出请求后无法解析成功回执的客户端错误。调用方必须认为外部投递可能已发生。
- `TelegramDeliveryError`：明确的 HTTP 4xx（包括 429）、Telegram `ok=false`、非法 PNG、消息过长或缺少配置等确定失败。

V1.3.1 多关键词日报通道中，文字和图片的 `max_attempts` 均固定为 1。其他历史通道是否改变重试规则不在本次范围内。

## 10. API 和脚本行为

`POST /reports/daily/multi/send` 对不确定、失败或正在发送状态不调用 Telegram，返回可区分的 409 业务错误。

`GET /reports/daily/multi/status` 对外显示：

```json
{
  "status": "text_uncertain",
  "text_sent": false,
  "photo_sent": false,
  "manual_action_required": true
}
```

状态接口不暴露 Token、Chat ID、代理地址或消息全文。

`ops/daily_update.sh` 的内部报告请求超时从 30 秒调整为 120 秒，以覆盖图表渲染以及一次文字和一次图片请求。内部 Telegram 请求仍有自己更短的超时，因此不会让 API 无界等待。

脚本遇到 409 或 `manual_action_required=true` 时必须输出“投递结果不确定，需要人工检查”并非零退出，不重新抓取已存在快照，不重发文字或图片。

## 11. Migration 007

新 migration 只扩展 `ops.report_deliveries` 状态检查和字段组合约束，不自动修改历史投递记录。

部署后，2026-08-22 的旧 `failed` 记录不通过 SQL 伪造 message ID。用户调用 `recover-photo?confirm_text_visible=true` 时，服务根据显式的人工确认将这四份记录预占为 `photo_sending`，成功后记为 `completed_text_uncertain`。

Migration 必须可重复执行，不修改已部署的 `006_add_daily_job_snapshots.sql`。

## 12. 错误处理

- 快照不齐：409，不发送。
- 采集范围不一致：409，不发送。
- 四份投递状态不一致：409，不发送。
- 已完成：返回 `already_sent`，不发送。
- 正在发送：409，不发送。
- 结果不确定：409，需要人工操作，不自动重试。
- 恢复接口未显式确认文字可见：409，不发送。
- Telegram 图片结果不确定：记录 `photo_uncertain`，返回 502，不自动重试。

## 13. 测试设计

### Telegram 通道测试

- 文字超时时只调用 HTTP `post` 1 次并抛出 `TelegramDeliveryUncertain`。
- 图片超时时只调用 HTTP `post` 1 次并抛出 `TelegramDeliveryUncertain`。
- HTTP 4xx 仍是明确失败。
- HTTP 5xx 作为结果不确定处理，不在同一任务内重试。
- 正常响应仍返回正整数 message ID。

### 多关键词服务测试

- Telegram 文字调用前四份记录已预占为 `text_sending`。
- 文字超时后四份记录均为 `text_uncertain`。
- 再次调用普通发送不调用文字发送器。
- 文字成功、图片超时时，文字 message ID 保留，状态为 `photo_uncertain`。
- 恢复接口未确认文字可见时，文字和图片发送器都不调用。
- 恢复接口确认文字可见后，文字发送器不调用，图片发送器只调用 1 次。
- 从 `text_uncertain` 或旧 `failed` 补图成功后，四份记录均为
  `completed_text_uncertain`；从旧 `partial_failed` 补图成功后为
  `completed`。两种情况都共享同一 photo message ID。
- 两个并发请求只有一个取得发送权，发送器总调用数为 1。
- `completed` 和 `completed_text_uncertain` 重跕调用均返回 `already_sent`。

### API、Migration 和脚本测试

- 新恢复接口无 Token 时在数据库访问前返回 401。
- `confirm_text_visible=false` 返回 409。
- Migration 包含新状态、合法字段组合和外键保护，可重复执行。
- 脚本调用内部报告 API 的 timeout 为 120 秒。
- 脚本遇到不确定状态时不重新抓取已有快照，不重发 Telegram。

## 14. 部署和 2026-08-22 恢复

1. 在修复部署前停止 `jobflow-daily-update.timer`，防止明天再次调用旧逻辑。
2. 本机完成定向测试、非 PostgreSQL 回归、Ruff、Bash 语法、Compose 解析和差异检查。
3. 只在用户明确授权后 commit/push。
4. Ubuntu 执行 `git pull --ff-only origin main`。
5. 通过服务器 Mihomo 构建新 API/ETL 镜像。
6. 执行 migration 007。
7. 重建 API 容器，等待 `/ready` 成功。
8. 查询 2026-08-22 四份快照和投递状态，确认仍是预期的旧 `failed` 记录。
9. 调用一次 `recover-photo?snapshot_date=2026-08-22&confirm_text_visible=true`。
10. 验收 Telegram 只新增一张正式热力图，没有新文字。
11. 查询状态为 `completed_text_uncertain`、`photo_sent=true`、`manual_action_required=false`。
12. 重新启用 `jobflow-daily-update.timer`，检查下一次为 2026-08-23 09:00 Asia/Shanghai。

## 15. 验收标准

- 网络超时时单阶段不出现 3 次自动 Telegram 投递。
- 不确定状态不被普通定时任务当作 `pending`。
- 只补图恢复不调用文字发送器。
- 2026-08-22 不重新抓取和 ETL，Telegram 只补一张热力图。
- 数据库不伪造文字 message ID，最终状态诚实表达文字回执不确定。
- 不暴露 `.env`、Telegram Token、Chat ID、代理订阅或其他私密配置。
- 2026-08-23 正式 timer 在新状态机下独立验收，不因 2026-08-22 恢复成功而提前宣称连续运行通过。

## 16. 风险与延后项

- Telegram 没有幂等键，单次请求仍可能“已送达但状态不确定”；本设计使其停在人工检查点，不会自动扩大成重复消息。
- 如果只补图本身变成 `photo_uncertain`，本次不实现再次强制重试接口；需要用户先查看 Telegram 再设计下一个显式恢复步骤。
- 今日已送达的 3 条重复文字由用户在 Telegram 中手动删除，不在 JobFlow 自动处理范围内。
