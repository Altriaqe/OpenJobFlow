# JobFlow 查询与 AI 双模式报告设计

日期：2026-08-15

状态：设计已确认，等待实施计划

## 1. 目标

JobFlow 的核心仍是招聘数据查询机器人。系统从 PostgreSQL 只读统计结果中读取城市岗位数量，并通过 Telegram 私聊发送报告。

在保留现有报告接口、Bearer Token 鉴权和 Telegram 发送链路的基础上，增加两种报告模式：

- `query`：默认模式。使用数据库指标和固定规则生成正式的中文数据简报，不调用 AI。
- `ai`：可选模式。使用同一批数据库指标调用 OpenAI 兼容服务/OpenAI 兼容接口，生成自然语言总结后发送。

对外可以规范表述为“招聘数据查询与智能总结机器人”，但必须区分可核验的查询结果、离线测试结果和真实 AI 服务调用。

## 2. 接口

保留现有接口：

```http
POST /reports/cities/send
Authorization: Bearer <REPORT_TRIGGER_TOKEN>
```

新增可选查询参数：

```http
POST /reports/cities/send?mode=query
POST /reports/cities/send?mode=ai
```

规则：

1. 不传 `mode` 时默认使用 `query`。
2. 只接受 `query` 和 `ai`，其他值返回 HTTP `422`。
3. Bearer Token 鉴权仍在数据库查询前执行。
4. 鉴权失败时不得查询数据库、调用 AI 或发送 Telegram。
5. 空数据时两种模式都返回 `skipped`，不发送消息。

成功响应保持兼容：

```json
{
  "status": "sent",
  "city_count": 10
}
```

## 3. 数据流

```text
POST /reports/cities/send?mode=query|ai
        ↓
Bearer Token 鉴权
        ↓
读取 mart.city_job_counts
        ↓
根据 mode 选择报告生成器
   ┌──────────────┴──────────────┐
   ↓                             ↓
固定规则查询报告                  OpenAI 兼容服务/OpenAI 总结
   └──────────────┬──────────────┘
                  ↓
            Telegram Bot 私聊
                  ↓
              返回发送结果
```

两种模式读取同一份指标，不改变 ETL、PostgreSQL 表结构或数据写入流程。

## 4. 模块边界

```text
src/jobflow/db/analytics.py
→ 只读 mart.city_job_counts，返回城市和岗位数量

src/jobflow/reports/service.py
→ 编排查询、模式选择、报告生成和发送

src/jobflow/reports/query_report.py（计划新增）
→ 生成固定模板查询报告和确定性观察

src/jobflow/ai/openai_summary.py
→ 仅在 mode=ai 时调用 OpenAI 兼容服务/OpenAI 兼容接口

src/jobflow/channels/telegram.py
→ 发送最终文本，不判断报告来源

src/jobflow/api/reports.py
→ Bearer Token 鉴权、mode 参数校验和 HTTP 响应
```

查询报告生成器不访问网络、不写数据库、不读取密钥。

## 5. 查询模式报告模板

查询模式使用固定结构，所有数值来自输入指标，所有观察来自明确规则：

```text
━━━━━━━━━━━━━━━━━━━━
JobFlow｜招聘市场数据简报
━━━━━━━━━━━━━━━━━━━━

报告时间：<生成时间>
数据范围：当前数据库已入库职位
统计维度：城市岗位数量
数据状态：只读查询结果

一、核心指标
• 覆盖城市：<城市数> 个
• 职位总量：<职位总数> 个
• 最高城市岗位数：<城市>，<数量> 个
• 前三城市职位占比：<占比>

二、城市岗位分布
排名  城市       岗位数     占比
<排名表>

三、数据观察
<根据排名、占比和差异计算的固定规则文本>

四、业务提示
<只陈述当前数据可支持的查询提示>

五、口径说明
• 统计对象：当前数据库中的职位记录。
• 岗位数量按系统当前聚合结果计算。
• 本报告不代表完整招聘市场规模。
• 本报告未推断薪资、技能需求、增长趋势或因果关系。

━━━━━━━━━━━━━━━━━━━━
JobFlow｜数据查询服务
━━━━━━━━━━━━━━━━━━━━
```

建议拆分为以下函数，便于测试和后续扩展：

```text
build_query_report_header()
build_query_report_metrics()
build_query_report_observations()
build_query_report()
```

固定规则示例：

- 最高城市取岗位数第一名。
- 前三城市占比为前三名岗位数除以职位总量。
- 只有达到预设阈值时，才显示“岗位集中”等描述。
- 没有历史快照时，明确说明不能判断趋势。
- 不生成数据库中不存在的薪资、技能、增长原因或因果结论。

## 6. AI 模式

AI 模式复用现有 `generate_city_report()`，输入仍然是 `list_city_job_counts()` 返回的城市和岗位数量。

AI 提示词必须继续限制：

- 只根据输入城市和岗位数量总结事实。
- 不编造薪资、技能、趋势、原因或不存在的数字。
- 说明统计口径是当前数据库中的岗位数量。

AI 服务异常时返回现有的 `503 report service unavailable`，不自动降级为查询模式，避免调用者误以为获得了 AI 总结。

## 7. 测试与验收

Windows 离线测试至少覆盖：

- 默认无 `mode` 使用 `query`。
- `mode=query` 不调用 AI 生成器。
- `mode=ai` 调用 AI 生成器一次。
- 两种模式都调用 Telegram 发送器。
- 空数据不调用 AI、不发送 Telegram。
- 非法 `mode` 返回 HTTP `422`。
- 原有报告、Telegram、API 和非集成测试继续通过。

真实验证分开记录：

1. 查询模式：Ubuntu API 查询数据库并真实发送 Telegram。
2. AI 模式：Ubuntu API 通过 OpenAI 兼容服务 真实生成并发送 Telegram。

只有实际外部请求成功，才能称为真实服务联调；Mock 测试只能证明代码分支和错误处理逻辑。

## 8. 不在本次范围内

- 不增加定时调度。
- 不增加新的 Telegram 群组或企业微信渠道。
- 不修改 PostgreSQL 表结构和 ETL 流程。
- 不把查询模式描述为 AI 生成。
- 不自动提交或推送 Git。
