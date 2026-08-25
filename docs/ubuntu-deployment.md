# Ubuntu 局域网部署与运行手册

更新日期：2026-08-15

本文记录 JobFlow V1.1 至 V1.3 在 Ubuntu 服务器上的通用部署和运行方式。所有命令使用 Compose v2+ 形式 `docker compose`，不要使用旧版 `docker-compose`。

`<SSH_USER>`、`<SERVER_IP>`、`<JOBFLOW_DIR>`、`<API_HOST>` 和 `<API_PORT>` 都是占位符。执行命令前替换为自己的值，不要保留尖括号。

## 当前服务器

```text
Ubuntu：22.04.5 LTS
用户：<SSH_USER>
IP：<SERVER_IP>
项目目录：<JOBFLOW_DIR>
访问范围：<LAN_CIDR> 局域网
```

## 运行前检查

```bash
ssh <SSH_USER>@<SERVER_IP>
cd <JOBFLOW_DIR>
git status --short --branch
docker --version
docker compose version
```

当前服务器使用 Docker Engine 29 和 Docker Compose v5.4.0。旧 Compose 1.29.2 曾出现 `KeyError: 'ContainerConfig'`，因此后续统一使用用户级 Compose 插件与 `docker compose` 命令。

## 首次部署或代码更新

```bash
cd <JOBFLOW_DIR>
git pull --ff-only
docker compose build
```

若只想保持已验收的数据部署版本，先确认目标提交，不要在尚未准备外部服务配置时直接启动报告接口联调。2026-08-15 的 Ubuntu 数据部署验收停点为 `e73cf18`；`0ba1f13` 包含 AI 报告和外部消息渠道代码。

## 环境变量

服务器本地 `.env` 至少包含这些变量名：

```text
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_PORT
API_BIND_HOST
API_PORT
```

接入报告模块时再配置：

```text
OPENAI_API_KEY
OPENAI_MODEL
OPENAI_BASE_URL
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
REPORT_TRIGGER_TOKEN
```

使用以下命令限制权限：

```bash
chmod 600 .env
```

不要在文档、聊天、截图或 Git 中显示 `.env` 实际值。Telegram Bot Token 和 Chat ID 只保存在服务器。

不要在文档、聊天、截图或 Git 中显示 `.env` 实际值。

## Windows 上传快照

在 Windows PowerShell 或 CMD 中执行，路径按实际文件位置替换：

```cmd
scp boss_jobs.json <SSH_USER>@<SERVER_IP>:<JOBFLOW_DIR>/data/raw/inbox/boss_jobs.json
```

服务器上的目录需要允许容器非 root 用户穿越：

```bash
cd <JOBFLOW_DIR>
chmod 711 data/raw data/raw/inbox
```

`711` 只给其他用户目录穿越权限，不开放目录写权限。不要为了省事改成 `777`。

## 标准启动顺序

```bash
cd <JOBFLOW_DIR>

docker compose up -d postgres
docker compose run --rm migrate
docker compose run --rm etl /data/raw/inbox/boss_jobs.json
docker compose up -d api
docker compose ps
```

顺序含义：

```text
postgres 健康
→ migration 创建或升级表结构
→ ETL 处理指定快照
→ API 提供查询
```

`migrate` 和 `etl` 是一次性任务，成功后容器退出并由 `--rm` 删除；`postgres` 和 `api` 是常驻服务。

如果当天没有新快照，只需启动现有数据库和 API：

```bash
docker compose up -d postgres api
docker compose ps
```

## Ubuntu 本机验收

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
curl --fail 'http://127.0.0.1:8000/analytics/cities?limit=3'
curl --fail 'http://127.0.0.1:8000/analytics/salaries/cities?limit=3'
curl --fail 'http://127.0.0.1:8000/analytics/skills?limit=3'
```

Windows 局域网访问：

```text
http://<API_HOST>:<API_PORT>/health
http://<API_HOST>:<API_PORT>/ready
http://<API_HOST>:<API_PORT>/docs
```

`/health` 成功只证明 API 进程存活；`/ready` 成功才证明 PostgreSQL 依赖可用。最后还要调用真实分析接口，才能证明业务链路完整。

## 查看状态和日志

```bash
docker compose ps
docker compose logs --tail=100 api
docker compose logs --tail=100 postgres
docker compose logs --tail=100 migrate
```

ETL 是一次性容器，命令运行时会直接显示日志和退出状态。如果失败，先保留完整输出，再检查快照路径、目录权限、环境变量、数据库健康和 migration。

## 停止与再次启动

停止 API 和数据库但保留容器：

```bash
docker compose stop api postgres
```

再次启动：

```bash
docker compose start postgres api
docker compose ps
```

停止并删除容器网络，但保留 PostgreSQL 数据卷：

```bash
docker compose down
```

不要随意执行 `docker compose down -v`，`-v` 会删除 PostgreSQL 数据卷。

## 网络与防火墙

当前 `.env` 使用：

```text
API_BIND_HOST=<SERVER_IP>
API_PORT=8000
```

UFW 边界：

```text
OpenSSH：允许
8000/tcp：只允许 <LAN_CIDR>
5432/tcp：不向局域网开放
```

数据库只绑定 `127.0.0.1`；API、ETL 和 migration 在 Compose 内部网络使用服务名 `postgres` 连接数据库。

## 网络代理（可选）

JobFlow 默认可以在不配置代理的情况下部署。如果服务器网络能够直接访问所需外部服务，将 `JOBFLOW_HTTP_PROXY` 和 `JOBFLOW_HTTPS_PROXY` 留空。

如果所在网络需要代理，应用容器可以使用部署者自己维护的代理服务：

```text
代理主机：<PROXY_HOST>
代理端口：<PROXY_PORT>
```

代理端必须允许 Docker 应用容器访问。公开项目只提供标准环境变量接口，不包含代理客户端、节点、订阅链接或个人配置。

应用容器的运行时代理通过 Compose 从 `.env` 注入，不需要每次 SSH 后重复 `export`：

```dotenv
JOBFLOW_HTTP_PROXY=http://<PROXY_HOST>:<PROXY_PORT>
JOBFLOW_HTTPS_PROXY=http://<PROXY_HOST>:<PROXY_PORT>
JOBFLOW_NO_PROXY=postgres,localhost,127.0.0.1
```

修改 `.env` 后使用 `docker compose up -d --force-recreate api` 让新容器读取配置。

注意：容器中的 `127.0.0.1` 是容器自身，不是 Ubuntu 宿主机。如果代理运行在宿主机或另一个容器中，必须使用应用容器可解析、可连接的地址。代理凭据和订阅只能保存在部署者自己的服务器中，不得进入 Git、README、截图或日志。

### V1.2 内置可选覆盖

不想自行维护外部代理地址时，可以使用仓库提供的 Mihomo 覆盖文件。默认 `compose.yaml` 不会自动启用它。

首次准备：

```bash
cd <JOBFLOW_DIR>
mkdir -p runtime/mihomo/providers
cp deploy/mihomo/config.example.yaml runtime/mihomo/config.yaml
nano runtime/mihomo/config.yaml
chmod 600 runtime/mihomo/config.yaml
```

只在服务器私有文件中替换 `<YOUR_PROXY_SUBSCRIPTION_URL>`。`runtime/` 已被 Git 忽略。

如果服务器已经在仓库外维护 Mihomo 配置，可以不复制模板，只在 `.env` 增加：

```dotenv
MIHOMO_CONFIG_DIR=/etc/jobflow-mihomo
```

这是宿主机配置目录，不是代理地址。不要执行 `cat` 输出私有配置；可用 `sudo test -f /etc/jobflow-mihomo/config.yaml` 只检查文件是否存在。

一键启动：

```bash
docker compose \
  -f compose.yaml \
  -f compose.proxy.yaml \
  up -d postgres api mihomo
```

检查：

```bash
docker compose \
  -f compose.yaml \
  -f compose.proxy.yaml \
  ps

docker inspect "$(docker compose -f compose.yaml -f compose.proxy.yaml ps -q mihomo)" \
  --format 'restart={{.HostConfig.RestartPolicy.Name}} port_bindings={{json .HostConfig.PortBindings}}'
```

正常应显示 `restart=unless-stopped`，并且 `port_bindings` 为 `{}` 或 `null`。配置语法通过后仍需在 API 容器内调用真实外部服务，才能确认订阅和节点可用。

## V1.1 每日更新与 Telegram

当前宿主机 systemd 服务：

```text
jobflow-xvfb.service
jobflow-boss-chrome.service
jobflow-daily-update.service
jobflow-daily-update.timer
```

检查状态：

```bash
systemctl is-active jobflow-xvfb.service
systemctl is-active jobflow-boss-chrome.service
systemctl status jobflow-daily-update.timer --no-pager
systemctl list-timers --all | grep jobflow
```

Xvfb 与 Chrome 应为 `enabled + active`；正式 timer 应为 `enabled + active (waiting)`，计划每天 `09:00 Asia/Shanghai` 触发。

每日脚本：

```text
<JOBFLOW_DIR>/ops/daily_update.sh
```

运行顺序：

```text
flock 单实例锁
→ boss_cdp_raw.py --check
→ 四城市各抓取 1 页
→ {"jobs": [...]} 原子快照
→ docker compose run --rm etl
→ POST /reports/cities/send?mode=query
→ Telegram 私聊
```

报告 Token 只从 API 容器环境读取，不写入宿主机脚本和 journal。Telegram 失败不会回滚 ETL，但脚本非零退出，systemd service 标记失败。

2026-08-16 已使用独立 5 分钟 transient timer 完成真实验收：systemd service `status=0/SUCCESS`，ETL completed，报告接口返回 `city_count=4`，手机 Telegram 私聊真实收到 397 个当前岗位的中文查询简报。正式每天 09:00 timer未被测试修改。

Chrome 服务重启后可能需要通过 VNC 人工登录一次。日常 timer 只复用长期运行的 Chrome，不应每天重启浏览器。

## 笔记本服务器合盖运行（可选）

如果 Ubuntu 本身安装在笔记本上，默认合盖可能触发休眠，Docker、Chrome、timer 和网络都会暂停。先检查是否已有覆盖：

```bash
sudo grep -R --no-filename \
  -E '^[[:space:]]*HandleLidSwitch' \
  /etc/systemd/logind.conf \
  /etc/systemd/logind.conf.d 2>/dev/null ||
  echo "NO_LID_OVERRIDE"
```

需要让服务器合盖继续运行时，创建 `/etc/systemd/logind.conf.d/99-jobflow-lid.conf`：

```ini
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
```

应用并检查：

```bash
sudo systemctl restart systemd-logind
systemctl is-active systemd-logind
sudo systemd-analyze cat-config systemd/logind.conf |
  grep -E '^HandleLidSwitch'
```

不能只看配置文本。应从另一台电脑持续 `ping <SERVER_IP>`，合盖数分钟后再请求 `curl --fail http://<SERVER_IP>:<API_PORT>/ready`。合盖运行必须保持供电、网络和散热；屏幕熄灭不等于服务器停止。

## 已完成与未完成边界

已完成：Ubuntu 容器构建、migration、PostgreSQL 聚合、API 健康/就绪检查、三个分析接口、Windows 局域网访问、四城市抓取与 ETL、Xvfb/Chrome 长期服务、每日 timer 部署、5 分钟自动触发、Telegram 真实送达、V1.2 Compose 代理迁移、无外部端口验证、真实报告发送、Mihomo 重启后外联复验、笔记本合盖不休眠与 `/ready` 真实验收，以及 Windows 本地机关机后的服务器代理正式定时推送。2026-08-19 进一步完成 V1.3 四城市 × 每城三页、180 条样本、ETL、每日不可变快照、对比简报、城市构成 PNG 和 Telegram 图文真实送达，脚本退出码为 0。

未完成：整台 Ubuntu 重启恢复、连续多日运行、登录失效通知、后续版本多关键词与更大抓取范围、公网域名、Caddy、HTTPS、完整鉴权、备份恢复、监控告警。Chrome 151 前台 Target 修复在 Ubuntu 仍是 scraper 工作区补丁；本机修复已提交并创建上游 PR `#68`，但尚未合并。

项目整体上下文与下一步见 [`project-handoff.md`](project-handoff.md)。
