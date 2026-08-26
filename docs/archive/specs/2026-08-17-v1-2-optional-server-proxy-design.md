# JobFlow V1.2 可选服务器代理与一键部署设计

更新日期：2026-08-17

## 背景

JobFlow V1.1 的 Ubuntu 定时任务已经完成抓取、ETL 和 Telegram 报告链路。2026-08-17 正式 09:00 任务因 API 容器依赖已关闭的 Windows 代理而在 Telegram 阶段失败；同日使用 Ubuntu 独立 Mihomo 容器完成 `getMe`、真实 `mode=query` 报告和容器重启验收。

V1.2 将这一经验整理为公开、可选、无个人秘密的服务器代理部署能力。默认本地 Docker 部署保持不变；只有网络受限的服务器才启用代理覆盖文件。

## 目标

- 提供独立 `compose.proxy.yaml`，不污染默认 `compose.yaml`。
- 提供 Mihomo 配置模板，个人订阅只使用占位符。
- 使用一条 Compose 命令启动 PostgreSQL、API 和 Mihomo。
- Mihomo 代理端口只在 Docker 内部网络暴露，不发布宿主机端口。
- API 通过服务名 `mihomo:7890` 使用代理。
- 默认直连用户无需安装或配置 Mihomo。
- README、Ubuntu 部署、架构、交接和知识库同步记录 V1.2。

## 非目标

- 不把个人订阅、节点、Token 或 Provider 缓存提交 Git。
- 不解决 Docker daemon 拉取镜像所需的宿主机代理。
- 不让 Mihomo 成为局域网公共代理。
- 不修改 ETL、PostgreSQL、报告内容、抓取范围或 systemd timer。

## 文件设计

```text
compose.yaml                              默认直连部署，不变
compose.proxy.yaml                        可选服务器代理覆盖
deploy/mihomo/config.example.yaml         可公开复制的配置模板
runtime/mihomo/config.yaml                用户私有配置，Git 忽略
runtime/mihomo/providers/                 Provider 缓存，Git 忽略
```

`compose.proxy.yaml` 新增 `mihomo` 服务，并覆盖 `api.environment`：

```text
HTTP_PROXY=http://mihomo:7890
HTTPS_PROXY=http://mihomo:7890
NO_PROXY=postgres,mihomo,localhost,127.0.0.1
```

Mihomo 使用固定镜像 `metacubex/mihomo:v1.19.30`、`restart: unless-stopped` 和可写配置目录。覆盖文件只写 `expose: 7890`，绝不写 `ports`。

## 用户流程

默认直连：

```bash
cp .env.example .env
docker compose up -d postgres api
```

服务器代理：

```bash
mkdir -p runtime/mihomo/providers
cp deploy/mihomo/config.example.yaml runtime/mihomo/config.yaml
nano runtime/mihomo/config.yaml
chmod 600 runtime/mihomo/config.yaml
docker compose -f compose.yaml -f compose.proxy.yaml up -d postgres api mihomo
```

模板中的 `<YOUR_PROXY_SUBSCRIPTION_URL>` 必须由部署者在自己的服务器替换，不进入提交、截图和日志。

## 安全边界

- `runtime/` 整体进入 `.gitignore`。
- 配置模板只含占位符。
- Mihomo 不发布宿主机端口。
- API 的 `NO_PROXY` 保留 PostgreSQL 与本机地址。
- README 明确容器 `127.0.0.1` 不是宿主机。
- 公开文档只写通用命令；真实服务器路径和维护细节进入个人知识库，但仍不记录订阅正文。

## 验收层级

1. 静态契约测试验证镜像、覆盖文件、占位符、Git 忽略和零端口发布。
2. `docker compose ... config --quiet` 验证合并配置。
3. 默认 Compose 仍能独立解析。
4. Ubuntu 从当前独立容器迁移为 Compose 管理后，验证状态、端口、DNS、`getMe` 和真实报告。
5. 下一次正式 09:00 timer 与连续多日运行仍是后续稳定性验收。

## 回滚

停止覆盖栈中的 Mihomo，清空或恢复 `.env` 代理入口，再用默认 `compose.yaml` 重建 API。代理失败不回滚已经提交的 ETL 和 PostgreSQL 数据。
