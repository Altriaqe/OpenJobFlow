# OpenJobFlow 项目文档

这里记录 OpenJobFlow 的当前实现、架构、部署边界、运维状态和历史设计。代码、migration、测试结果和真实运行证据是完成状态的最终依据；历史计划不自动代表已经实现。

## 入口文档

- [`architecture.md`](architecture.md)：正式系统架构、模块边界、数据流、部署和安全边界。
- [`project-handoff.md`](project-handoff.md)：当前 Git 状态、已验证功能、未完成事项和新对话交接入口。
- [`../README.md`](../README.md)：英文项目首页、Quick Start 和公开能力说明。
- [`../README.zh-CN.md`](../README.zh-CN.md)：中文项目首页和复现步骤。
- [`assets/jobflow-demo.png`](assets/jobflow-demo.png)：使用合成数据生成的趋势图示例。

## 按任务阅读

### 部署与运行

- [`guides/ubuntu-deployment.md`](guides/ubuntu-deployment.md)：Ubuntu、自托管 Docker、每日任务和恢复边界。
- [`guides/wechat-official-draft.md`](guides/wechat-official-draft.md)：微信公众号文章包、草稿创建和排障。
- [`guides/wechat-test-account.md`](guides/wechat-test-account.md)：微信测试号配置与验收。
- [`guides/wechat-article-download.md`](guides/wechat-article-download.md)：Windows 下载和校验文章包。

### 开发与设计

- [`development/README.md`](development/README.md)：当前开发资料索引。
- [`development/learning-notes.md`](development/learning-notes.md)：通用诊断顺序和实现经验。
- [`reference/data-sources.md`](reference/data-sources.md)：数据源和合规边界。

### 历史材料

- [`operations/`](operations/)：已发生的运行验收和故障恢复记录。
- [`archive/README.md`](archive/README.md)：已完成、替代或不再作为当前计划的设计材料。

## 文档维护规则

- 新对话先读 `project-handoff.md`，再读 `architecture.md` 和对应运行指南；
- 功能完成后只记录已验证的实现和证据，不把计划写成完成；
- 架构边界变化时更新 `architecture.md`；部署命令变化时更新对应指南；
- 每日运行记录只保留项目本身的简短状态，具体私有环境信息不进入公开仓库；
- 不记录 `.env` 实际值、密码、API Key、Webhook、Token、Cookie、私钥、真实服务器地址或真实数据；
- 公开项目只使用占位符和合成示例，真实运行产物留在部署环境。
