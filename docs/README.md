# JobFlow 文档

这里记录 JobFlow 的当前实现、运行方式、部署边界和演进设计。代码、migration、测试结果和真实运行证据是完成状态的最终依据；历史设计中的“计划”不自动代表已经实现。

## 公开仓库入口

- [`../README.md`](../README.md)：英文项目首页与完整 Docker Quick Start。
- [`../README.zh-CN.md`](../README.zh-CN.md)：中文项目首页与完整 Docker 复现步骤。
- [`assets/jobflow-demo.png`](assets/jobflow-demo.png)：使用完全虚构数据生成的趋势图示例。

## 第一次运行项目

- [`guides/ubuntu-deployment.md`](guides/ubuntu-deployment.md)：Ubuntu 从拉取代码到启动、ETL、验证和停机的运行手册。
- [`guides/wechat-test-account.md`](guides/wechat-test-account.md)：微信测试号配置、Migration、手动验收和安全恢复。

根目录 README 面向公开用户，提供从合规 JSON 快照开始的最短可运行路径；`guides/` 提供更完整的部署和外部渠道验收步骤。

## 理解项目结构和数据边界

- [`reference/architecture.md`](reference/architecture.md)：当前模块边界、数据流和已实现范围。
- [`reference/data-sources.md`](reference/data-sources.md)：快照来源、使用边界和后续替换方式。
- [`reference/platform-evolution-design.md`](reference/platform-evolution-design.md)：AI 数据中台、只读机器人和数据源演进方向。

## 恢复和继续开发

- [`project-handoff.md`](project-handoff.md)：当前目标、Git 状态、验证结果和下一步，是新对话与恢复开发的固定入口。
- [`development/README.md`](development/README.md)：当前版本仍在开发或等待验收的设计与计划。
- [`development/learning-notes.md`](development/learning-notes.md)：开发过程中遇到的问题、诊断顺序和修复原因。

## 运行证据与历史

- [`operations/2026-08-25-daily-update-production-acceptance.md`](operations/2026-08-25-daily-update-production-acceptance.md)：API 就绪等待修复后的正式日报验收记录。
- [`archive/README.md`](archive/README.md)：已完成或被替代的历史设计与实施计划。

## 维护规则

- 功能完成后同步更新 `project-handoff.md` 的进度、验证结果和下一步；
- 启动命令或服务器配置变化时更新 `guides/ubuntu-deployment.md`；
- 架构边界变化时更新 `reference/architecture.md`；
- 当前开发资料进入 `development/`，完成或被替代后移入 `archive/`；
- 不在文档中记录 `.env` 实际值、密码、API Key、Webhook、Token、Cookie 或私钥；
- 公开文档只使用服务器、用户名和目录占位符，真实个人环境只记录在私有知识库；
- 不把“代码已写”表述为“外部服务已真实联调”或“生产环境已上线”。
