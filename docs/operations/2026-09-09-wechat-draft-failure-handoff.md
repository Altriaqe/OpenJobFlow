---
project: JobFlow
type: operation
date: 2026-09-09
status: resolved
tags:
  - project/jobflow
  - wechat
  - operations
  - handoff
---

# 2026-09-09 微信公众号草稿失败排障交接

> 后续状态更新（2026-09-10）：维护者已确认当日公众号草稿成功发表。本文件保留原始失败诊断和安全边界，作为已解决事件记录；不再把它作为当前待修复故障。后续投放仍须先查询数据库和公众号后台，确认无同日草稿后才允许重试。

## 结论

本次每日链路没有整体失败。BOSS 抓取、四关键词 ETL、文章包生成和 Telegram 投递均已有成功证据；原始诊断时失败边界位于微信公众号草稿创建阶段。后续由维护者确认草稿已成功发表，本事件已关闭。

这是一条开发/运维记录，不构成版本更新，也不代表 React 可视化已经完成或系统已经达到公网生产级稳定性。

## 已确认事实

```text
BOSS 抓取：成功
四关键词 ETL：成功
任务日志合并数据：180 条
文章包：生成成功
文章包 manifest.new_job_count：268
Telegram：sent
微信公众号草稿：失败
systemd：最终在微信草稿阶段失败
```

文章包包含：

```text
article.html
article.md
cover.png
trend.png
manifest.json
```

当日文章包目录为：

```text
<JOBFLOW_DIR>/runtime/reports/2026-09-09/wechat/
```

任务日志中的“合并数据 180 条”和 `manifest.new_job_count=268` 属于不同统计口径，后续排查不得擅自合并或替换这两个数字。

## 已完成诊断

1. 文章包最初因 API 容器用户无权写入 `runtime` 而生成失败；修复目录属主和读写权限后，文章包成功生成。
2. 一次图片缺失判断漏掉了 `wechat/` 子目录，属于诊断命令路径错误，不是微信接口返回的错误。
3. 正式账号环境变量存在；Token 请求返回 HTTP 200、无微信错误码，并取得 Token。
4. 趋势图临时素材上传返回 HTTP 200、无微信错误码。
5. 封面永久素材上传返回 HTTP 200、无微信错误码。
6. `build_draft_payload` 与 `create_draft` 的实际函数签名已读取。
7. 本次没有取得 `draft/add` 的最终响应；因此不能写成草稿已创建，也不能据此判断 AppID、权限或 IP 白名单已经是根因。

## 重要版本边界

服务器容器中的 `jobflow.channels.wechat_draft` 当前可见函数包括：

```text
get_wechat_access_token
upload_image
build_draft_payload
create_draft
```

此前假设的 `_load_package` 在服务器模块中不存在。下一步必须先确认服务器 Git ref、API 镜像和容器内源码，再与本地 `<LOCAL_JOBFLOW_DIR>` 对照。不能凭旧函数名直接修改本地代码或部署。

## 暂停期间的安全边界

- 不重跑完整每日任务；
- 不重新发送 Telegram；
- 不直接重复调用 `draft/add`；
- 不删除数据库草稿状态、微信素材或公众号后台草稿；
- 不重启 API、systemd timer 或 BOSS Chrome；
- 不把 Token、AppSecret、Webhook、Cookie、Chat ID、完整素材 ID 或完整请求 URL 写入日志、截图或文档。

微信请求发生过真实 Token 和素材上传诊断，因此本次排障不能描述为“完全只读”；但没有完成最终草稿创建验证。

## 下一次继续顺序

```text
只读确认服务器 Git / 镜像 / 容器 / /ready
→ 查询 2026-09-09 的草稿数据库状态
→ 登录正确公众号后台检查是否已有同日草稿
→ 对照服务器与本地 wechat_draft 实际源码
→ 只在确认没有同日草稿后，取得 draft/add 的脱敏 errcode/errmsg
→ 根据真实错误码做最小修复
→ 单独验证微信草稿，不重跑 Telegram
```

## 相关入口

- [`project-handoff.md`](../project-handoff.md)
- [`../guides/wechat-official-draft.md`](../guides/wechat-official-draft.md)
- [`../reference/architecture.md`](../reference/architecture.md)
