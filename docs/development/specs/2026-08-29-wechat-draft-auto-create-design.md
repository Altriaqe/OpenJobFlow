# V1.3.5 微信公众号自动创建草稿设计

## Summary

V1.3.4 已实现服务器生成文章包、Windows 下载与校验，正式公众号仍需人工导入发布。V1.3.5 将每日 09:00 任务扩展为自动创建公众号草稿，维护者只需在后台审核并点击发布。Telegram 现有日报链路保持完全不变。

## Goal

在不自动发布公众号文章、不改变 Telegram 行为的前提下，完成以下链路：

```text
每日任务生成文章包
→ 上传封面和趋势图
→ 创建一篇公众号草稿
→ 维护者后台审核
→ 维护者手动发布
```

## Non-goals

- 不自动点击“发布”；
- 不使用浏览器自动化操作公众号后台；
- 不修改 Telegram 报告内容、发送状态机或时序；
- 不让微信失败回滚已成功的 ETL；
- 不自动重试结果不确定的微信请求；
- 不把真实 appid、appsecret、access_token、素材 ID、Cookie 或服务器配置写入代码、Git、日志或知识库。

## Architecture

```text
systemd timer
→ daily_update.sh
→ 采集与 ETL
→ Telegram 原有自动发送分支
→ 微信文章包生成
→ 草稿状态幂等检查
→ 上传封面和趋势图
→ 替换正文图片地址
→ 微信草稿创建
→ 数据库记录 created
→ 人工审核并发布
```

Telegram 与公众号草稿是两个独立分支。公众号草稿失败只记录自身失败状态，不改变 ETL 结果，也不阻止 Telegram 分支完成。

## Database state

新增独立 migration 和表 `wechat_draft_jobs`：

| 字段 | 约束 | 说明 |
| --- | --- | --- |
| `id` | primary key | 本地记录 ID |
| `report_date` | unique, not null | 业务日期，同一天只允许一条任务记录 |
| `status` | not null | `uploading`、`created` 或 `failed` |
| `draft_media_id` | nullable | 微信草稿标识；只保存平台返回的 ID |
| `cover_media_id` | nullable | 封面素材标识 |
| `trend_media_id` | nullable | 趋势图素材标识 |
| `error_code` | nullable | 脱敏后的错误类别 |
| `error_message` | nullable | 固定描述，不包含 token 或完整请求 URL |
| `created_at` | not null | 首次记录时间 |
| `updated_at` | not null | 最近状态更新时间 |

状态迁移：

```text
不存在 → uploading → created
                   └→ failed
```

已有 `created` 记录时直接跳过，不覆盖、不重复创建。已有 `failed` 记录时本轮不自动重试，保留文章包供人工兜底；后续如需重试，必须设计单独的人工确认入口。

## WeChat API boundary

使用服务器私有环境变量获取公众号凭据：

```text
WECHAT_APP_ID
WECHAT_APP_SECRET
```

客户端负责：

1. 获取短期 `access_token`，只在内存中使用；
2. 上传 `cover.png` 和 `trend.png`；
3. 将正文中的本地图片引用替换为微信素材 URL；
4. 调用草稿创建接口，提交标题、作者、摘要、封面素材和正文；
5. 返回脱敏后的成功或失败结果。

日志只允许记录固定阶段、日期、状态和错误类别，不记录 access token、secret、完整 API URL、Cookie 或正文中的敏感配置。

## Article mapping

- 标题：沿用文章包建议标题 `YYYY-MM-DD 每日新增岗位公告`；
- 作者：使用服务器私有配置中的通用作者名，未配置时草稿创建应明确失败，不猜测个人信息；
- 摘要：使用当日关键词、城市和新增岗位数量的聚合摘要；
- 封面：上传 `cover.png` 作为草稿封面；
- 正文：使用文章包的 HTML 内容，保留岗位分隔线、学历要求、薪资和明文岗位地址；
- 趋势图：上传 `trend.png` 并替换正文图片地址；
- 周对比：文章包存在周度摘要时一并保留，否则不添加空模块。

## Failure isolation

```text
文章包缺失或校验失败 → draft status=failed
素材上传失败         → draft status=failed
草稿创建明确失败     → draft status=failed
网络超时/断连         → draft status=failed，标记结果不确定，不自动重试
```

以上情况均不得：

- 回滚已经提交的 ETL 事务；
- 删除文章包；
- 修改 Telegram 状态；
- 自动再次调用普通创建接口。

## Daily integration

`daily_update.sh` 保持现有 Telegram 与文章生成并行结构。公众号草稿创建在文章包成功生成后进入独立步骤；其退出状态单独记录。是否让整个 daily service 最终返回失败，需要在实施阶段根据当前脚本的渠道汇总契约补充测试，不能通过隐式副作用改变 Telegram 结果。

## Acceptance criteria

1. 服务器每日任务完成后，指定日期最多存在一篇公众号草稿任务记录。
2. 草稿包含正确标题、作者、封面、趋势图和正文图片 URL。
3. 同日重复执行不会创建第二篇草稿，也不会覆盖已有草稿。
4. 草稿创建失败会写入 `failed` 和脱敏错误类别，文章包仍保留。
5. 草稿失败不改变 ETL 结果和 Telegram 发送结果。
6. access token、secret、Cookie、服务器地址和完整请求 URL 不出现在日志、测试输出或公开文档。
7. 离线单元测试、migration/数据库测试和服务器一次真实联调通过。
8. 正式公众号发布仍由维护者人工审核并点击发布。

## Open risks

- 未认证个人公众号虽然已通过草稿箱数量接口权限探测，但封面上传、正文图片上传和草稿创建权限仍需真实联调确认。
- 微信素材接口可能对图片大小、格式和永久/临时素材类型有额外限制；联调时只使用当天真实文章包，不发布文章。
- 作者字段是否必须填写取决于草稿接口校验结果；缺失时应记录明确失败，不自动填入个人信息。
- 草稿创建成功后，微信平台内部状态仍需人工在后台确认；创建成功不等于正式发布成功。
