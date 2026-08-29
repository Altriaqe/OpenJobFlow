# 微信公众号自动草稿配置与排错指南

本文说明 JobFlow V1.3.5 如何把每日文章包自动写入正式微信公众号草稿箱。该能力只创建草稿，不调用发布接口；标题、正文、封面和趋势图仍应由维护者在公众号后台检查后手动发布。

所有示例都使用占位符。真实 AppID、AppSecret、Token、服务器地址、IP、素材 ID 和草稿 ID 只能保存在私有部署环境中，不得提交到 Git、日志或截图。

## 1. 每日链路与故障边界

```text
systemd timer
→ daily_update.sh
→ 采集、ETL、每日快照
→ 并行执行
   ├─ Telegram 图文推送
   └─ 微信文章包生成
      → 上传封面永久素材
      → 上传正文趋势图
      → 创建正式公众号草稿
→ 维护者后台审核
→ 手动正式发布
```

Telegram 和微信是独立分支。微信草稿失败不会回滚 ETL，也不会撤销 Telegram；文章包会保留，Windows 下载工具仍可作为人工兜底。JobFlow 不自动正式发布，也不自动重试失败或结果不确定的草稿请求。

## 2. 测试号与正式公众号不是同一账号

微信公众平台测试号和正式公众号拥有不同的 AppID、AppSecret、关注用户和接口权限。测试号模板消息成功，不代表正式公众号的素材或草稿接口可用。正式联调必须在目标公众号后台重新取得账号信息并检查接口权限。

部署前确认：

1. 登录的是准备接收草稿的正式公众号，而不是测试号后台。
2. 在公众号后台取得该账号自己的 AppID，并生成或重置 AppSecret。
3. 将服务器的公网出口 IP 加入微信 API IP 白名单。
4. 账号具备永久素材、正文图片和草稿接口权限。
5. 真实配置只写入服务器私有 `.env`，文件权限保持 `600`。

示例变量名：

```dotenv
WECHAT_APP_ID=<YOUR_OFFICIAL_ACCOUNT_APP_ID>
WECHAT_APP_SECRET=<YOUR_OFFICIAL_ACCOUNT_APP_SECRET>
WECHAT_DRAFT_AUTHOR=<YOUR_PUBLIC_AUTHOR_NAME>
JOBFLOW_NO_PROXY=postgres,mihomo,localhost,127.0.0.1,api.weixin.qq.com
```

`WECHAT_OPENID` 和 `WECHAT_TEMPLATE_ID` 属于保留的测试号模板链路；正式草稿创建不依赖这两个值。

## 3. 部署 V1.3.5

先检查 Git 状态，避免覆盖服务器未提交文件：

```bash
cd <JOBFLOW_DIR>
git status --short --branch
git pull --ff-only origin main
```

应用 Migration 010 并重建 API 镜像。已经使用过早期 migration 的服务器，应先确认自己的 migration 记录和执行策略，不要盲目重放旧脚本：

```bash
docker compose -f compose.yaml -f compose.proxy.yaml build api
docker compose -f compose.yaml -f compose.proxy.yaml run --rm migrate
docker compose -f compose.yaml -f compose.proxy.yaml up -d --no-deps --force-recreate api
docker compose -f compose.yaml -f compose.proxy.yaml ps api
curl --fail http://127.0.0.1:8000/ready
```

Migration 010 创建 `ops.wechat_draft_jobs`，以日期作为唯一键记录 `uploading`、`created` 或 `failed`。它用于防止同一天重复创建草稿。

## 4. 手动验收顺序

先生成文章包，再创建草稿，最后查询状态。以下命令在 API 容器内读取私有 `REPORT_TRIGGER_TOKEN`，不会把 Token 写进 shell 历史：

```bash
REPORT_DATE=<YYYY-MM-DD>

docker compose -f compose.yaml -f compose.proxy.yaml exec -T api \
  python - "$REPORT_DATE" <<'PY'
import json
import os
import sys
import urllib.request

report_date = sys.argv[1]
token = os.environ["REPORT_TRIGGER_TOKEN"]
base = "http://127.0.0.1:8000/reports/daily/multi/wechat"

for method, path in (
    ("POST", f"/article/generate?snapshot_date={report_date}"),
    ("POST", f"/draft/create?snapshot_date={report_date}"),
    ("GET", f"/draft/status?snapshot_date={report_date}"),
):
    request = urllib.request.Request(
        base + path,
        method=method,
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        print(json.dumps(json.load(response), ensure_ascii=False))
PY
```

预期顺序是文章 `generated`、草稿 `created`、状态 `has_draft=true`。随后登录正确的公众号后台检查标题、作者、中文、封面、趋势图、岗位分隔线和明文岗位地址。只有后台可见且排版正确，才算草稿链路验收；正式发布仍需人工操作。

## 5. 三个微信接口为什么不能混用

| 用途 | 接口 | 关键成功字段 | 在 JobFlow 中的作用 |
| --- | --- | --- | --- |
| 封面永久素材 | `/cgi-bin/material/add_material` | `media_id` | 作为 `thumb_media_id` |
| 正文图片 | `/cgi-bin/media/uploadimg` | `url` | 替换正文中的本地 `trend.png` |
| 创建草稿 | `/cgi-bin/draft/add` | `media_id` | 标识微信已经接受的草稿 |

正文图片接口通常返回可嵌入文章的 `url`，不能强制要求它同时返回 `media_id`。永久素材则必须取得 `media_id`。把两种响应按同一结构校验，会把正常响应误判为失败。

## 6. 中文与排版兼容原理

### UTF-8 JSON

草稿请求必须发送真实 UTF-8 字节：

```python
body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
headers = {"Content-Type": "application/json; charset=utf-8"}
```

若使用默认的 ASCII 转义，微信侧可能把 `\u4eca\u65e5` 一类内容保存为字面文本，后台就会出现乱码式转义字符串。

### 内联样式

微信公众号编辑器会清理 `<style>`、CSS class、完整 HTML 外壳和部分布局规则。文章卡片的颜色、间距、边框和岗位分隔线应直接写在元素的 `style` 属性中。标题解析也必须允许 `<h1>` 带属性：

```python
r"<h1\b[^>]*>(.*?)</h1>"
```

只匹配 `<h1>...</h1>` 会在加入内联样式后找不到标题，进而让草稿创建失败。

## 7. 幂等、失败和删除边界

`ops.wechat_draft_jobs.report_date` 唯一约束保证同一天只会首次认领一次：

```text
不存在记录 → uploading → created
                   └→ failed
```

- `created`：再次调用只返回现有状态，不重复创建。
- `failed`：默认不自动重试，因为网络中断时微信可能已经收到请求。
- `uploading`：可能仍在处理，也可能是进程中断留下的状态；先查微信后台和日志。
- 删除错误草稿：先在公众号后台人工删除可见草稿，再确认数据库日期和状态；不要批量删除素材或直接清空状态表。

若确需重置单日失败记录，必须先确认公众号后台没有同日草稿，并备份数据库，再由维护者针对明确日期处理。公开文档不提供可误删全表的命令。

## 8. 排错顺序

按下列顺序逐层确认，前一层没有证据时不要跳到后一层改代码：

1. **代码版本**：`git log -5 --oneline` 是否包含 V1.3.5 草稿提交。
2. **镜像版本**：拉取代码后是否重新 build 并 recreate API；只 `git pull` 不会更新旧容器里的代码。
3. **API 路由**：`/openapi.json` 是否包含 `/draft/create` 和 `/draft/status`。
4. **Migration**：`ops.wechat_draft_jobs` 是否存在，字段和约束是否为 Migration 010。
5. **文章包**：日期、清单、`article.html`、`cover.png`、`trend.png` 和 SHA-256 是否一致。
6. **网络路径**：容器是否能访问 `api.weixin.qq.com`；受限网络中确认 `JOBFLOW_NO_PROXY` 已让微信直连，同时不改变 Telegram 的 Mihomo 路径。
7. **Access Token**：正式公众号 AppID/AppSecret 是否成对、是否已重置、是否来自正确账号。
8. **IP 白名单**：错误码 `40164` 时核对微信看到的公网出口 IP，而不是局域网或 Tailscale 地址。
9. **接口权限**：错误码 `48001` 通常表示账号或接口权限不支持；确认登录账号类型和能力。
10. **素材上传**：分别检查永久封面的 `media_id` 与正文图的 `url`。
11. **草稿请求**：检查 UTF-8 请求体、标题解析和返回错误码；不输出 Token 或完整请求 URL。
12. **公众号后台**：确认查看的是与 AppID 对应的正式公众号草稿箱。

常见现象：

| 现象 | 优先检查 | 原因 |
| --- | --- | --- |
| 接口 404 | 镜像版本、OpenAPI 路由 | 容器仍运行旧镜像 |
| 数据库报表不存在 | Migration 010 | 新代码已运行但数据库未升级 |
| `40164` | IP 白名单 | 微信拒绝未登记的出口 IP |
| `48001` | 账号类型和接口权限 | 当前公众号无对应 API 权限 |
| `ReadTimeout` | 代理、DNS、`NO_PROXY` | 请求未稳定到达微信，结果可能不确定 |
| 正文图上传被判失败 | 响应校验 | `uploadimg` 返回 `url` 而非必有 `media_id` |
| 中文显示 `\uXXXX` | JSON 编码 | 请求体不是显式 UTF-8 |
| 样式丢失 | 微信 HTML 清洗 | 使用了 `<style>` 或 class 而非内联样式 |
| 标题缺失 | `<h1>` 正则 | 标题标签带有 `style` 等属性 |
| build 下载依赖失败 | Docker 镜像源、代理 | 构建网络故障，不是草稿业务代码故障 |

## 9. 日常巡检

```bash
cd <JOBFLOW_DIR>
git status --short --branch
systemctl status jobflow-daily-update.service --no-pager
docker compose -f compose.yaml -f compose.proxy.yaml ps
curl --fail http://127.0.0.1:8000/ready
journalctl -u jobflow-daily-update.service -n 120 --no-pager
```

日志中应分别看到 Telegram、微信文章和微信草稿状态。不要用“草稿已创建”代替 ETL、Telegram、timer 或正式发布的验收证据；这些是不同层级。

## 10. 相关文档

- [微信测试号配置与服务器验收](wechat-test-account.md)
- [Windows 公众号文章包下载指南](wechat-article-download.md)
- [Ubuntu 局域网部署与运行手册](ubuntu-deployment.md)
- [架构与实现状态](../reference/architecture.md)
- [项目当前状态与开发交接](../project-handoff.md)
