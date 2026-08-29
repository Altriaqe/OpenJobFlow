# V1.3.5 微信公众号自动创建草稿实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在每日任务生成文章包后，自动上传封面与趋势图并创建一篇微信公众号草稿，同时保持 Telegram、ETL 和正式发布人工边界不变。

**Architecture:** 新增独立 `wechat_draft_jobs` 状态表，以 `report_date` 唯一约束实现同日幂等。微信客户端负责 token、素材上传、正文图片地址替换和草稿创建；每日 Shell 在文章包成功生成后调用独立草稿步骤，失败只记录草稿状态，不修改 Telegram 或 ETL 结果。

**Tech Stack:** Python、urllib、PostgreSQL migration、Docker Compose、Bash、Pytest。

## Global Constraints

- Telegram 现有报告内容、发送状态机和调用时序不得修改。
- 草稿创建成功不等于发布成功；不得自动点击发布。
- 失败不自动重试，不回滚 ETL，不删除文章包。
- 不记录真实 appid、appsecret、access_token、Cookie、服务器地址或完整请求 URL。
- 真实凭据只从服务器环境变量 `WECHAT_APP_ID`、`WECHAT_APP_SECRET` 读取。

---

### Task 1: 草稿状态 migration 与数据访问层

**Files:**
- Create: `migrations/010_wechat_draft_jobs.sql`
- Create: `src/jobflow/db/wechat_drafts.py`
- Test: `tests/db/test_wechat_drafts.py`

**Interfaces:**
- `claim_wechat_draft(connection, report_date) -> bool`
- `record_wechat_draft_created(connection, report_date, draft_media_id, cover_media_id, trend_media_id) -> None`
- `record_wechat_draft_failed(connection, report_date, error_code, error_message) -> None`
- `get_wechat_draft_status(connection, report_date) -> WechatDraftStatus | None`

- [ ] 编写 migration：创建 `wechat_draft_jobs`，`report_date UNIQUE NOT NULL`，状态限制为 `uploading/created/failed`，时间字段默认当前时间。
- [ ] 编写测试：首次 claim 成功；第二次 claim 返回 False；created/failed 状态可记录和读取；错误信息长度和敏感字段不写入。
- [ ] 实现事务内 `INSERT ... ON CONFLICT DO NOTHING` claim，调用方提交事务。
- [ ] 运行 `pytest tests/db/test_wechat_drafts.py -q`，预期全部通过。

### Task 2: 微信素材与草稿客户端

**Files:**
- Create: `src/jobflow/channels/wechat_draft.py`
- Create: `tests/channels/test_wechat_draft.py`

**Interfaces:**
- `get_access_token(app_id: str, app_secret: str, post=...) -> str`
- `upload_image(access_token: str, path: Path, post=...) -> UploadedWechatImage`
- `create_draft(access_token: str, payload: dict, post=...) -> str`
- `build_draft_payload(article_html: str, title: str, author: str, digest: str, thumb_media_id: str) -> dict`

- [ ] 先写 HTTP mock 测试：成功 token、图片上传、草稿创建；微信明确错误映射为脱敏异常；响应和日志不得包含 secret/token。
- [ ] 实现 urllib 客户端：token 只保存在内存；上传 `cover.png`、`trend.png`；草稿 payload 使用标题、作者、摘要、封面 ID 和替换图片 URL 的 HTML。
- [ ] 实现本地 `trend.png` 替换为微信返回 URL，禁止保留 `src="trend.png"`。
- [ ] 运行 `pytest tests/channels/test_wechat_draft.py -q`，预期全部通过。

### Task 3: 文章包草稿编排服务

**Files:**
- Create: `src/jobflow/reports/wechat_draft_service.py`
- Create: `tests/reports/test_wechat_draft_service.py`

**Interfaces:**
- `create_wechat_draft_from_article(connection, report_date: date, article_dir: Path, author: str) -> DraftResult`

- [ ] 测试文章包缺失、已有 created、上传失败、草稿成功四条路径。
- [ ] 实现顺序：校验六文件和 manifest → claim → 上传封面/趋势图 → 读取 HTML → 构造 payload → 创建草稿 → 记录 created；任何异常记录 failed 并保留文章包。
- [ ] 明确 failed 不自动重试；返回状态只包含日期、状态和脱敏错误类别。
- [ ] 运行 `pytest tests/reports/test_wechat_draft_service.py -q`，预期全部通过。

### Task 4: 接入每日 Shell，保持 Telegram 不变

**Files:**
- Modify: `ops/daily_update.sh`
- Modify: `tests/ops/test_daily_update_script.py`

- [ ] 先增加契约测试：草稿步骤只能位于文章生成成功之后；原 Telegram 调用和并行 wait 文本保持不变；脚本不调用微信普通模板发送接口。
- [ ] 增加独立 `create_wechat_draft` Shell 函数，调用 API/worker 使用当天文章目录和服务器私有作者配置；不把 secret 拼入日志。
- [ ] 处理草稿步骤退出码并记录状态；不得改变 Telegram 的退出码或重复发送逻辑。
- [ ] 运行 `pytest tests/ops/test_daily_update_script.py -q` 和 Bash 语法检查 `bash -n ops/daily_update.sh`。

### Task 5: API/配置与可观测状态

**Files:**
- Modify: `src/jobflow/api/reports.py`
- Modify: `src/jobflow/reports/wechat_service.py`
- Test: `tests/api/test_reports.py` 或现有报告路由测试文件

- [ ] 增加受保护的草稿状态查询入口，只返回日期、状态、错误类别和是否存在草稿 ID，不返回 token、素材 URL 或服务器路径。
- [ ] 保持作者配置缺失时明确失败，不猜测个人信息。
- [ ] 增加路由测试：created、failed、not found 三种响应；未授权请求返回现有鉴权错误。

### Task 6: 公开文档、离线回归和服务器联调

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/reference/architecture.md`
- Modify: `docs/guides/wechat-test-account.md`
- Modify: `docs/project-handoff.md`

- [ ] 文档说明 V1.3.5 为“自动创建草稿、人工点击发布”，Telegram 不变，失败隔离。
- [ ] 运行完整非数据库回归、公开文档测试、Ruff、脚本测试和 `git diff --check`。
- [ ] Ubuntu 执行 migration、重建 API、先用当天文章包真实创建草稿；只核对后台草稿，不点击发布。
- [ ] 验收同日重复运行不产生第二篇草稿，封面和趋势图可见，失败时文章包仍可人工导入。
- [ ] 真实联调结果脱敏记录；未获得用户明确授权前不提交或推送。

## Self-review

- 覆盖设计说明中的状态表、素材上传、正文替换、幂等、失败隔离、人工发布和 Telegram 独立边界。
- 所有函数签名在相邻任务中定义，无未完成占位项或未定义接口。
- 服务器真实联调安排在离线测试之后，且不包含自动发布。
