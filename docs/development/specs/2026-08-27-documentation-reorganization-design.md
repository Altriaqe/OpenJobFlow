# OpenJobFlow 文档目录整理设计

日期：2026-08-27

## 1. 背景

`docs/` 已经包含公开部署教程、架构说明、项目交接、开发排错、功能设计、实施计划和生产验收记录，但不同用途的文档仍混合在顶层或 `superpowers/` 下。现有 `docs/README.md` 提供了基础索引，不过只列出部分设计文档，不能清晰区分当前教程、正在进行的开发资料和历史记录。

本次整理的目标是让公开用户、项目维护者和历史追溯者从不同入口快速找到正确文档，同时保证仓库内部链接和文档测试继续有效。

## 2. 目标

- 按使用场景重新组织真实文件目录；
- 保留 `docs/README.md` 作为文档总入口；
- 保留 `docs/project-handoff.md` 作为恢复当前开发状态的固定入口；
- 把公开教程、架构参考、当前开发资料、生产验收和历史资料分开；
- 只在当前开发区保留 V1.3.2 微信相关设计与计划；
- 把已完成或已被替代的设计与计划移入归档；
- 修复根 README、内部 Markdown 和测试中的全部受影响路径；
- 保留当前 `docs/project-handoff.md` 的未提交内容；
- 不引入个人配置、真实凭据、服务器地址或个人绝对路径。

## 3. 非目标

- 不重写历史 PRD 和历史实施计划的原始内容；
- 不删除设计、计划、生产验收或图片资产；
- 不修改业务代码、数据库结构、部署配置和定时任务；
- 不在本轮重新设计根目录公开 README；
- 不创建文档网站或引入 MkDocs、Docusaurus 等新依赖；
- 不提交、不推送，也不创建 Pull Request。

## 4. 目标目录结构

```text
docs/
├─ README.md
├─ project-handoff.md
├─ guides/
│  ├─ ubuntu-deployment.md
│  └─ wechat-test-account.md
├─ reference/
│  ├─ architecture.md
│  ├─ data-sources.md
│  └─ platform-evolution-design.md
├─ development/
│  ├─ README.md
│  ├─ learning-notes.md
│  ├─ specs/
│  └─ plans/
├─ operations/
│  └─ 2026-08-25-daily-update-production-acceptance.md
├─ archive/
│  ├─ README.md
│  ├─ specs/
│  └─ plans/
└─ assets/
   └─ jobflow-demo.png
```

`project-handoff.md` 不移动，因为它是新对话、换电脑和暂停开发后的固定恢复入口。`operations/` 与 `assets/` 的职责已经明确，因此保持现状。

## 5. 文件归属

### 5.1 公开操作指南

移动到 `docs/guides/`：

```text
ubuntu-deployment.md
wechat-test-account.md
```

这两份文档回答“如何部署、配置和验收”，面向准备复现或维护运行环境的用户。

### 5.2 架构与边界参考

移动到 `docs/reference/`：

```text
architecture.md
data-sources.md
platform-evolution-design.md
```

这三份文档回答“系统怎么组成、数据从哪里来、未来如何演进”，不承担逐步部署教程职责。

### 5.3 当前开发资料

移动到 `docs/development/`：

```text
learning-notes.md
```

当前 `docs/superpowers/specs/` 和 `docs/superpowers/plans/` 中只保留以下 V1.3.2 文档，并分别移动到 `docs/development/specs/` 和 `docs/development/plans/`：

```text
2026-08-26-wechat-official-daily-delivery-design.md
2026-08-26-wechat-official-daily-delivery.md
2026-08-27-wechat-article-package-permissions-design.md
2026-08-27-wechat-article-package-permissions.md
2026-08-27-documentation-reorganization-design.md
```

后续生成的本次实施计划也进入 `docs/development/plans/`。

新增 `docs/development/README.md`，说明当前开发资料的阅读顺序、完成状态和事实边界。

### 5.4 历史归档

现有 `docs/superpowers/specs/`、`docs/superpowers/plans/` 中除 V1.3.2 当前文档外的文件，全部移动到对应的 `docs/archive/specs/` 或 `docs/archive/plans/`。

现有 `docs/archive/` 内容继续保留。新增 `docs/archive/README.md`，明确：

- 归档文件用于追溯历史决策；
- 历史计划不代表当前实现；
- 历史命令不应直接作为当前部署教程；
- 当前事实以代码、测试、`project-handoff.md` 和服务器证据为准。

移动完成后删除空的 `docs/superpowers/` 目录。

## 6. 文档入口设计

`docs/README.md` 按读者目标组织：

```text
第一次运行项目                 → guides/
理解架构和数据边界             → reference/
恢复当前开发状态               → project-handoff.md
参与当前版本开发               → development/
查看真实生产验收               → operations/
追溯旧设计和旧计划             → archive/
```

总入口不再逐条平铺大量历史规格，而是链接到 `development/README.md` 和 `archive/README.md`。这样新增历史文档时不需要不断扩张顶层索引。

## 7. 链接迁移策略

移动文件后统一更新：

- 根目录 `README.md`；
- 根目录 `README.zh-CN.md`；
- `docs/README.md`；
- `docs/project-handoff.md`；
- 所有 Markdown 中引用的相对路径；
- 当前设计和实施计划中的仓库文件路径；
- `tests/docs/test_public_assets.py` 中固定检查的文档路径。

不在旧位置保留跳转占位文件，否则顶层目录仍然混乱。所有仓库内引用在同一轮变更中迁移到新路径。

历史文档内用于说明当时任务范围的路径只有在它会形成失效链接时才更新；纯粹作为历史文本出现、且不承担导航功能的旧路径保持原样，避免改写历史语境。

## 8. 现有修改保护

开始移动前记录：

```bash
git status --short --branch
git diff -- docs/project-handoff.md
```

`docs/project-handoff.md` 已有 V1.3.2 最新交接修改。本次只允许在其现有内容上更新受影响链接，不能用旧版本覆盖，也不能把该文件恢复到 `HEAD`。

暂存时使用明确文件列表，不使用 `git add .`。本轮只整理和验证工作区，不执行提交或推送。

## 9. 验收标准

### 9.1 目录和差异

- 目标目录结构完整；
- `docs/superpowers/` 已无剩余文件；
- 没有文档被删除或遗漏；
- `git status` 只出现预期移动、新索引和链接更新；
- `docs/project-handoff.md` 原有未提交状态内容仍然存在。

### 9.2 链接

- 扫描全部 Markdown 相对链接；
- 扫描全部本地图片引用；
- 根目录中不再引用已经移动的旧路径；
- 当前开发文档和归档索引中的链接全部可解析；
- 文档正文不残留承担导航作用的 `docs/superpowers/` 路径。

### 9.3 内容安全

- 不出现真实 `.env` 值；
- 不出现密码、API Key、Webhook、Token、Cookie 或私钥；
- 不新增个人用户名、服务器地址、订阅地址或个人绝对路径；
- 历史设计不被错误表述为当前完成状态。

### 9.4 自动检查

```bash
git diff --check
pytest -q tests/docs/test_public_assets.py
```

另外运行仓库级 Markdown 链接检查和旧路径残留扫描。若测试仍依赖旧路径，先确认测试表达的是公开契约，再随新目录更新期望值。

## 10. 失败处理与回退

- 先生成完整移动清单，再逐类移动；
- 每完成一类文件就检查链接差异；
- 任何文档数量不一致或链接缺失都停止回写；
- 只恢复本轮新增或移动的文件，不覆盖用户原有未提交修改；
- 不使用 `git reset --hard` 或批量恢复整个工作区。

## 11. 完成边界

本次完成表示：目录结构、索引、链接和文档测试已经整理并通过本地验收。

它不表示：功能代码有新版本、服务器已经更新、微信定时推送已经验收、功能分支已经推送或 Pull Request 已创建。
