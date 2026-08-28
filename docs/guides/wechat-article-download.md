# V1.3.4 Windows 一键下载微信公众号文章包

脚本路径：`scripts/download-wechat-article.ps1`。

它只使用一次递归 SCP 将服务器文章包拉到本地临时目录，再完成文件校验和中文文件名修正；不触发采集、不发送 Telegram/微信消息，也不自动发布公众号。

## 首次设置

在 PowerShell 中设置当前窗口的服务器参数（值不会写进 Git）：

```powershell
$env:JOBFLOW_SERVER_USER = '你的 Ubuntu 用户名'
$env:JOBFLOW_SERVER_HOST = '你的 Tailscale 地址或主机名'
$env:JOBFLOW_REMOTE_ROOT = '/home/你的用户名/services/jobflow'
```

## 每日运行

CMD 或直接双击推荐使用启动器：

```cmd
scripts\download-wechat-article.cmd
```

PowerShell 也可以直接运行底层脚本：

```powershell
cd OpenJobFlow
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\download-wechat-article.ps1
```

脚本默认使用 Windows 当天日期。也可以指定已经生成的日期：

```cmd
scripts\download-wechat-article.cmd -Date 2026-08-28
```

```powershell
.\scripts\download-wechat-article.ps1 -Date 2026-08-28
```

运行时 SCP 会在终端中要求输入一次密码；密码不会显示，也不会被脚本保存。配置 SSH 密钥后可以免输密码。

为了避免每天重复输入服务器用户名、主机和项目目录，可以在 Windows 中一次性保存三个非秘密环境变量：

```cmd
setx JOBFLOW_SERVER_USER "<SSH_USER>"
setx JOBFLOW_SERVER_HOST "<SERVER_HOST>"
setx JOBFLOW_REMOTE_ROOT "<JOBFLOW_REMOTE_ROOT>"
```

关闭并重新打开终端后生效。它们不包含密码，也不会进入 Git；SSH 密码仍由终端安全输入。

## 输出

成功后输出到：

```text
downloads\\wechat-YYYY-MM-DD\\wechat\\
├─ YYYY-MM-DD 每日新增岗位公告.md
├─ article.md
├─ article.html
├─ cover.png
├─ manifest.json
└─ trend.png
```

目标日期目录已经存在、远程快照不完整、日期无效、六个文件缺失或 `manifest.json` 日期不一致时，脚本会返回错误并停止，不覆盖已有文章。

## 发布边界

脚本完成后仍需人工：导入动态中文 Markdown、确认标题和作者、保存草稿、手机预览、确认岗位内容后发布。个人公众号的标题和作者不依赖 Markdown 自动填充。
