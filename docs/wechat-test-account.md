# 微信测试号配置与服务器验收

本文用于 OpenJobFlow V1.3.2。公开仓库不包含任何真实 `appsecret`、`openid`、模板 ID、报告 Token 或服务器地址。

## 能力边界

- 微信测试号自动接收聚合模板摘要；
- 同时生成 `runtime/reports/<日期>/wechat/` 文章排版包；
- 正式个人订阅号首版由维护者人工检查后发布；
- Telegram 与微信并行，状态独立；
- `uncertain` 状态禁止自动重发。

## 测试模板

在微信公众平台测试号后台创建 `JobFlow日报` 模板：

```text
{{first.DATA}}
报告日期：{{report_date.DATA}}
样本记录：{{total_jobs.DATA}}
新增样本：{{new_jobs.DATA}}
需求最高：{{top_keyword.DATA}}
优势组合：{{top_city.DATA}}
{{remark.DATA}}
```

模板字段只展示固定范围聚合样本，不包含公司名、岗位链接或个人配置。

## 私有配置

只在 Ubuntu 项目目录的私有 `.env` 中填写：

```dotenv
WECHAT_ENABLED=true
WECHAT_APP_ID=<YOUR_WECHAT_APP_ID>
WECHAT_APP_SECRET=<YOUR_WECHAT_APP_SECRET>
WECHAT_OPENID=<YOUR_WECHAT_OPENID>
WECHAT_TEMPLATE_ID=<YOUR_WECHAT_TEMPLATE_ID>
```

保持文件权限：

```bash
chmod 600 .env
```

不要把 `.env` 内容粘贴到终端记录、Issue、截图或聊天。

## 部署更新

在 Ubuntu 的 OpenJobFlow 项目目录执行：

```bash
git status --short --branch
git pull --ff-only
docker compose build api etl
mkdir -p runtime
APP_UID="$(docker compose run --rm --entrypoint id api -u)"
APP_GID="$(docker compose run --rm --entrypoint id api -g)"
sudo chown "$APP_UID:$APP_GID" runtime
chmod 755 runtime
docker compose run --rm migrate
docker compose up -d api
docker compose ps
```

Migration 009 只新增 `ops.report_channel_deliveries`，不会删除现有招聘数据。

## 手动发送验收

以下命令在 API 容器内读取私有 `REPORT_TRIGGER_TOKEN`，不会在宿主机命令行展开真实值：

```bash
docker compose exec -T api python - "$(date +%F)" <<'PY'
import json
import os
import sys
import urllib.request

report_date = sys.argv[1]
token = os.environ["REPORT_TRIGGER_TOKEN"]
request = urllib.request.Request(
    f"http://127.0.0.1:8000/reports/daily/multi/wechat/send?snapshot_date={report_date}",
    method="POST",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(request, timeout=120) as response:
    print(json.load(response))
PY
```

预期：手机测试号收到一条摘要，接口返回 `sent`；同日再次执行返回 `already_sent`。

文章包检查：

```bash
find "runtime/reports/$(date +%F)/wechat" -maxdepth 1 -type f -printf '%f\n' | sort
```

预期包含：`article.md`、`article.html`、`manifest.json`、`trend.png`。

## 状态和恢复

状态接口：

```text
GET /reports/daily/multi/wechat/status?snapshot_date=<YYYY-MM-DD>
```

如果状态为 `uncertain`，先检查手机。只有确认未收到时才调用：

```text
POST /reports/daily/multi/wechat/resend?snapshot_date=<YYYY-MM-DD>&confirm_not_received=true
```

不要对 `uncertain` 连续重试。超时或连接中断时，微信可能已经接收消息。

## 定时任务验收

手动发送成功后再运行一次每日任务：

```bash
bash -n ops/daily_update.sh
./ops/daily_update.sh
```

日志应显示 Telegram 和微信并行尝试，并分别输出状态。`WECHAT_ENABLED=false` 时微信安全跳过，不影响 Telegram。
