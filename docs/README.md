# JobFlow 文档

这里记录 JobFlow 的当前实现、运行方式、部署边界和演进设计。代码、migration、测试结果和真实运行证据是完成状态的最终依据；早期设计文档中的“计划”不自动代表已经实现。

## 公开仓库入口

- [`../README.md`](../README.md)：英文项目首页与完整 Docker Quick Start。
- [`../README.zh-CN.md`](../README.zh-CN.md)：中文项目首页与完整 Docker 复现步骤。
- [`assets/jobflow-demo.png`](assets/jobflow-demo.png)：使用完全虚构数据生成的 JobFlow 趋势图示例。

## 第一次阅读顺序

1. [`project-handoff.md`](project-handoff.md)：当前目标、进度、启动方法、验证结果和下一步，是新对话与恢复开发的入口。
2. [`ubuntu-deployment.md`](ubuntu-deployment.md)：Ubuntu 从拉取代码到启动、ETL、验证、停机的可执行步骤。
3. [`architecture.md`](architecture.md)：当前模块边界、数据流和已实现/未实现范围。
4. [`platform-evolution-design.md`](platform-evolution-design.md)：长期 AI 数据中台方向和权限原则。

根目录 [`README.md`](../README.md) 面向公开用户，只保留从合规 JSON 快照开始的最短可运行路径；本目录提供更完整的架构、部署、维护和交接细节。

## 当前文档

- [`wechat-test-account.md`](wechat-test-account.md)：V1.3.2 微信测试号配置、Migration、手动验收和安全恢复。

- [`project-handoff.md`](project-handoff.md)：项目当前状态与开发交接。
- [`architecture.md`](architecture.md)：目标架构、模块边界和当前实现状态。
- [`ubuntu-deployment.md`](ubuntu-deployment.md)：Ubuntu 22.04 局域网容器部署与运行手册。
- [`data-sources.md`](data-sources.md)：本地快照来源、使用边界和后续替换方式。
- [`learning-notes.md`](learning-notes.md)：开发过程中遇到的问题及修复原因。
- [`platform-evolution-design.md`](platform-evolution-design.md)：AI 数据中台、只读机器人和数据源演进设计。
- [`operations/2026-08-25-daily-update-production-acceptance.md`](operations/2026-08-25-daily-update-production-acceptance.md)：API 就绪等待修复后的 09:00 正式日报验收记录。
- [`superpowers/specs/2026-08-16-daily-telegram-delivery-design.md`](superpowers/specs/2026-08-16-daily-telegram-delivery-design.md)：V1.1 ETL 后自动发送 Telegram 的批准设计。
- [`superpowers/plans/2026-08-16-daily-telegram-delivery.md`](superpowers/plans/2026-08-16-daily-telegram-delivery.md)：V1.1 五分钟真实验收与仓库同步计划。
- [`superpowers/specs/2026-08-16-public-readme-and-server-knowledge-design.md`](superpowers/specs/2026-08-16-public-readme-and-server-knowledge-design.md)：公开 README、详细文档和私有服务器知识的分层设计。
- [`superpowers/plans/2026-08-16-public-readme-and-server-knowledge.md`](superpowers/plans/2026-08-16-public-readme-and-server-knowledge.md)：V1.1 公开文档收尾与安全校验计划。
- [`superpowers/specs/2026-08-17-v1-2-optional-server-proxy-design.md`](superpowers/specs/2026-08-17-v1-2-optional-server-proxy-design.md)：V1.2 可选服务器代理与一键部署设计。
- [`superpowers/plans/2026-08-17-v1-2-optional-server-proxy.md`](superpowers/plans/2026-08-17-v1-2-optional-server-proxy.md)：V1.2 实现、真实迁移与知识库同步计划。

## 设计与历史记录

- `superpowers/specs/`：近期功能设计，部分内容已实现，状态应结合交接文档确认。
- `superpowers/plans/`：近期实施计划，用于追溯任务拆分，不是运行手册。
- `archive/specs/`：早期设计规格。
- `archive/plans/`：早期实施计划。

## 维护规则

- 功能完成后同步更新 `project-handoff.md` 的进度、验证结果和下一步；
- 启动命令或服务器配置变化时同步更新 `ubuntu-deployment.md`；
- 架构边界变化时更新 `architecture.md`；
- 不在文档中记录 `.env` 实际值、密码、API Key、Webhook、Token、Cookie 或私钥；
- 公开文档只使用服务器、用户名和目录占位符，真实个人环境只记录在私有知识库；
- 不把“代码已写”表述为“外部服务已真实联调”或“公网生产环境已上线”。
