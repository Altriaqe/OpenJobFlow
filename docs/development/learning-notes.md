# 学习与排错记录

这份记录只保留开发中实际出现过的问题。每条内容写清现象、原因和处理方式，方便后续遇到相似错误时快速定位。

## 测试中的异常类型写错

为 HTTP 异常边界补测试时，失败用例一度使用了错误的异常类型。测试红灯虽然出现了，但失败原因与预期行为无关。

处理方式是先读完整 traceback，确认失败发生在断言目标上，再编写生产代码。TDD 的红灯需要证明“功能尚未实现”，语法错误、导入错误或测试自身写错不算有效红灯。

## `try` 范围过大

处理 `requests.Timeout` 时，`raise_for_status()` 和 `json()` 曾被一起放进同一个 `try`。这样会模糊网络超时、HTTP 状态错误和 JSON 解析错误的边界。

现在分别包住可能抛出对应异常的语句，只捕获需要转换的具体异常，并使用 `raise ... from exc` 保留异常链。

## 把字符串当作路径对象

快照读取函数的参数曾按字符串理解，却直接调用了路径相关方法。字符串没有 `Path` 提供的文件操作接口，类型标注与实际用法不一致。

修复后入口明确接收 `pathlib.Path`，测试也通过 `tmp_path` 创建临时文件。这样可以同时检查文件读取行为和类型约定。

## Git 状态 `MM`

`MM` 表示同一个文件既有已暂存修改，又有暂存后继续产生的未暂存修改。此时直接提交只会包含暂存区版本，工作区的新修改会留下。

提交前使用 `git diff` 查看未暂存内容，使用 `git diff --staged` 查看将要提交的内容，再根据实际情况重新执行 `git add`。

## amend 后进入 detached HEAD

修改历史提交时曾进入 detached HEAD。此时新的提交存在，但当前不在 `main` 分支上，继续提交容易让分支指针和实际工作脱节。

恢复时先通过 `git log --oneline --decorate` 确认目标提交，再让 `main` 指向正确位置。涉及历史修改前应先确认工作区干净，并记录当前分支和提交哈希。
# V1.3.2 微信公众号推送：模块怎么写、为什么这样写

## 当前状态

- 版本：V1.3.2（本机开发验证中，尚未提交或推送）。
- Telegram 保留；微信公众号作为独立渠道，可与 Telegram 并行执行。
- 测试号阶段发送模板摘要；正式个人订阅号先生成文章排版包，由人工检查后发布。
- 真实 `appsecret`、`openid`、模板 ID、Token 和服务器配置只放在部署者自己的私有环境。

## 微信渠道模块

文件：`src/jobflow/channels/wechat_official.py`

### 为什么拆成独立模块

渠道模块只负责“调用微信接口并解释回执”，不查询数据库、不生成日报，也不管理定时任务。这样做可以让报告逻辑保持确定性，也能单独测试网络失败、明确失败和结果不确定三种情况。

### 关键函数

- `_required`：统一处理显式参数和环境变量。缺少配置时在发出网络请求前失败。
- `get_wechat_access_token`：使用 `appid + appsecret` 获取短期令牌。令牌接口没有消息副作用，所以临时网络错误只做有限重试。
- `send_wechat_template`：发送模板摘要。微信返回明确错误时记录明确失败；超时、5xx 或无法解析可信回执时标记结果不确定，禁止自动重发。

### 为什么使用依赖注入

函数接受 `get`/`post` 参数，生产环境默认使用 `requests`，测试时传入 Mock。这样离线测试不会触网，也不会把真实凭据写进测试代码。

### 为什么固定官方 API 地址

微信令牌和模板发送地址写成官方 HTTPS 域名，不开放任意 Base URL 配置，避免部署者误把凭据发送到第三方地址。

## 入口关系

```text
ops/daily_update.sh
  → FastAPI /reports/daily/multi/wechat/send
    → 统一日报构建器
    → jobflow.channels.wechat_official
    → ops.report_channel_deliveries
```

脚本负责编排和退出码，API 负责鉴权与业务调用，渠道模块负责微信协议；每层只做自己的工作。

## 本机验证记录

```text
tests/channels/test_wechat_official.py：5 passed
tests/channels：23 passed
git diff --check：通过
```

当前 Windows 终端为 Python 3.11，未安装 Ruff；静态检查需在项目 Python 3.12 环境补跑。

## 全项目链路注释进度

第一批已为 `adapters`、`collectors`、`models` 和 `workers` 增加模块职责、入口函数和事务边界说明。注释只解释现有行为，没有改变 ETL 逻辑。

本机验证：`adapters`、`collectors`、`models` 共 41 项测试通过；Worker 测试因当前终端缺少 `psycopg` 依赖无法收集，需在完整项目环境补跑。`compileall` 和 `git diff --check` 通过。

第二批已为 `db` 和 `reports` 各模块补充职责说明，标明 mart 只读查询、raw/core 写入、批次生命周期、日/周环比计算、图表渲染和报告发送编排的边界。报告层测试（排除依赖 OpenAI 的服务测试）76 项通过；完整报告服务测试需在安装 `openai` 的项目环境补跑。

第三批已为 Telegram、企业微信、OpenAI、分析 API、健康检查和数据库依赖入口补充链路注释。渠道与报告回归合计 99 项通过；API 和 OpenAI 服务测试仍需完整项目依赖环境补跑。

## V1.3.2 文章排版包首个可行版本

`src/jobflow/reports/wechat_article.py` 目前提供纯离线 `WechatArticleData` 和 `write_wechat_article`：输入固定范围聚合指标与 PNG，输出机器稳定的 `article.md`、动态命名的 `YYYY-MM-DD 每日新增岗位公告.md`、`article.html`、`cover.png`、`trend.png` 和 `manifest.json`。公众号导入文件不含一级标题，避免文件名成为图文标题后正文再次重复标题；全部文件使用临时目录写入后替换，避免留下半套文章包。

本机验证：文章包测试 3 项通过。当前仅完成排版包契约，尚未接入 FastAPI、数据库状态或微信真实接口。

配置接线：`.env.example` 和 `compose.yaml` 已加入 `WECHAT_ENABLED`、`WECHAT_APP_ID`、`WECHAT_APP_SECRET`、`WECHAT_OPENID`、`WECHAT_TEMPLATE_ID`。默认关闭微信；Compose 只把变量传入 API 容器，真实值仍由部署者在服务器私有 `.env` 中维护。

## 个人公众号为什么改用岗位明文网址

真实发布测试表明，Markdown 导入后岗位外链会暂时显示，但个人公众号在保存草稿时可能清除外部超链接。这个限制发生在微信公众号发布层，不属于抓取、ETL 或 Telegram 渠道的问题，因此不应修改原始岗位数据，也不应影响 Telegram。

解决位置放在 `src/jobflow/reports/wechat_article.py` 的 WeChat 渲染器：继续读取并校验 `detail_url`，Markdown 输出“岗位原始地址（复制后打开）”加完整网址，HTML 输出经过转义的普通文字，不再生成 Markdown 或 HTML 超链接。当来源没有链接时隐藏整段。正文继续完整展示岗位信息，结尾增加数据来源和真实性提醒。这样即使网址不能直接点击，保存草稿后仍可见并可复制，同时保持各渠道职责独立。

2026-08-28 真实公众号复测通过：导入 Markdown 并保存草稿后，岗位名称、薪资、公司、地点、技能、岗位分隔线和“岗位原始地址（复制后打开）”均保留。该结果证明明文网址方案可以绕开个人公众号保存草稿时清除外部超链接的问题；是否自动变为可点击链接仍不作为验收条件。
