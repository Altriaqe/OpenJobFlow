# README 架构流程图更新设计

## Summary

当前 README 的 Architecture Mermaid 图只展示到 Telegram，未表达 V1.3.2/V1.3.3/V1.3.4 已完成的微信公众号链路和 Windows 文章包拉取工具，导致功能列表与流程图不一致。本次更新补齐每日定时入口、双自动消息渠道和正式公众号人工发布边界。

## Chosen approach

采用“主链路 + 双发布分支”的单张 Mermaid 流程图：

```text
systemd timer
→ daily_update.sh
→ JSON 快照
→ Source Adapter
→ ETL Worker
→ PostgreSQL
→ FastAPI 只读分析
→ 查询报告
→ Telegram 自动发送
→ 微信测试号自动模板摘要
→ 文章包生成
→ Windows 一键拉取与校验
→ 人工审核与公众号发布
```

图中将 Telegram 和微信测试号画成并行自动发送分支；文章包从每日任务生成后进入 Windows 本地工具，再进入人工审核与正式公众号发布。这样既体现自动化链路，也不会误导为公众号 API 全自动发布。

## Scope

- 更新 `README.md` 与 `README.zh-CN.md` 的 Architecture Mermaid 图。
- 更新 `docs/reference/architecture.md` 的对应流程图和说明（若该文档存在同一架构图）。
- 保留 AI 只接收 FastAPI 固定结构化结果、不直连 PostgreSQL 的边界说明。
- 保留 Windows 工具不参与采集、ETL、Telegram/微信自动发送和正式发布的边界说明。
- 不改业务代码、接口、定时任务配置或渠道行为。
- 不记录个人服务器地址、账号、Token、Cookie、密码或代理配置。

## Acceptance criteria

1. 中英文 README 的流程节点和分支语义一致。
2. Mermaid 图明确出现 `systemd timer`、`daily_update.sh`、Telegram、微信测试号、文章包、Windows 拉取和人工发布。
3. 正式公众号路径明确标注人工审核/发布，不写成 API 自动发布。
4. 图下方文字继续说明 AI 不直连数据库，渠道不参与采集、标准化和数据库写入。
5. 公开文档测试、敏感信息扫描和 `git diff --check` 通过。
6. 不包含真实运行凭据或个人基础设施配置。

## Open risks

- Mermaid 在不同 GitHub/Markdown 渲染器上的换行和节点宽度可能略有差异；节点文字保持简短，避免依赖复杂 HTML。
- 公众号人工发布仍是当前事实边界，未来若实现官方 API 发布需单独设计版本，不在本次范围内。
