# 2026-09-14 日报跨日恢复

## 事件

每日任务完成抓取后，ETL 先后遇到人民币薪资横线变体和周薪格式。服务器同时出现包索引和系统软件源网络错误，应用镜像无法稳定重建。

## 修复

- 薪资解析统一常见 Unicode 横线，并增加 `CNY_PER_WEEK`；
- Migration 012 更新主表与快照表约束；
- 005、006、008 的约束重建保持向前兼容，使当前重放式 migration runner 可重复执行；
- 刷新部署者自管的 Mihomo 订阅，分别验证 Telegram、PyPI 和 Debian 连通性；
- 重建应用镜像后，复用失败时保留的有效快照文件并补齐其余关键词。

## 验收

```text
定向测试：38 passed
Ruff：通过
Migration 001 至 012：重放成功
API：ready
四关键词快照：ready
微信公众号草稿：created
Telegram：sent，维护者确认收到
```

本次恢复跨过自然日，属于人工恢复，不是原定 timer 自动成功证据。代理订阅、节点、Token、Chat ID 和服务器私有配置均未进入仓库。

## 后续

- 继续观察下一次 timer；
- 优化 Dockerfile 依赖缓存层，减少源码小改后的重复下载；
- migration 失败时先检查约束完整性，不带错继续 ETL。
