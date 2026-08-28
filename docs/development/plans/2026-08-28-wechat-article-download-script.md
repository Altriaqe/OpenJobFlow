# OpenJobFlow V1.3.4 微信公众号文章包一键下载脚本实施计划

**Goal:** 提供 Windows PowerShell 脚本，将 Ubuntu 上指定或最近完整的微信公众号文章包下载、解压、校验并打开，保留人工导入与发布。

**Architecture:** 脚本用一次递归 SCP 把远程文章目录拉到本地临时目录，再完成文件校验、manifest 日期校验和中文文件名修正；不触发采集、不调用发送接口、不覆盖已有日期目录。日期默认使用本机当天，若远程包不存在则明确失败并提示等待定时任务。

**Tech Stack:** PowerShell 5+/7、OpenSSH `ssh/scp`、Windows `tar`、JSON manifest。

## 约束

- 服务器参数通过环境变量或交互输入，不写入脚本或仓库。
- Telegram 链路和公众号发布流程不变。
- 默认输出到 `downloads\\wechat-YYYY-MM-DD`。
- 已存在目标目录时停止，不覆盖。
- 校验六个文章包文件，动态 Markdown 重命名为日期公告名。
- 不自动填写公众号标题、作者，不自动发布。
- 不创建 Git commit 或 push。

## 实施步骤

1. 编写 `scripts/download-wechat-article.ps1`，实现参数校验、SCP 临时下载、中文文件名修正和 manifest 日期校验。
2. 编写 `docs/guides/wechat-article-download.md`，记录首次环境变量设置、每日运行、指定日期、密码输入、输出目录和人工发布边界。
3. 做 PowerShell AST 语法检查、临时 fixture 验证、真实文章包验收和 `git diff --check`。

## 运行接口

```powershell
.\\scripts\\download-wechat-article.ps1 [-Date yyyy-MM-dd] [-ServerUser <SSH_USER>] [-ServerHost <SERVER_HOST>] [-RemoteRoot <JOBFLOW_REMOTE_ROOT>]
```

脚本成功后输出：

```text
downloads\\wechat-YYYY-MM-DD\\wechat\\
├─ YYYY-MM-DD 每日新增岗位公告.md
├─ article.md
├─ article.html
├─ cover.png
├─ manifest.json
└─ trend.png
```

目标目录已存在、远程包不完整、日期无效或工具缺失时返回非零退出码且不删除已有文章。
