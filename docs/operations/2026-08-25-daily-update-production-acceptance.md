# 2026-08-25 每日任务正式运行验收

## 验收目的

验证 Ubuntu 重新开机后，`jobflow-daily-update.timer` 触发日报任务时能够等待 JobFlow API 就绪，避免 API 容器仍在启动而导致任务立即失败。

## 修复基线

```text
提交：47a14c0 fix: 等待 API 就绪后再运行每日任务
服务器仓库：main / origin/main = 47a14c0
API：GET /ready 返回 {"status":"ready"}
timer：active，每天 09:00 Asia/Shanghai
```

`ops/daily_update.sh` 在采集和数据库操作前轮询 `http://127.0.0.1:8000/ready`。总等待上限为 300 秒；超时后安全退出，不抓取、不写库、不发送 Telegram。

## 2026-08-25 正式运行证据

systemd 状态：

```text
Result=success
ExecMainStartTimestamp=Tue 2026-08-25 09:00:00 CST
ExecMainExitTimestamp=Tue 2026-08-25 09:14:33 CST
ExecMainStatus=0
```

任务于 09:00 准时启动，09:14:33 正常结束，总耗时 14 分 33 秒。

Telegram 实际收件：

```text
文字简报：1 条
可视化图片：1 张
重复文字：0 条
报告日期：2026-08-25
报告状态：趋势基线建立中
```

“趋势基线建立中”表示当前尚缺少符合相同数据口径的前一自然日基线，不代表发送失败。完成下一自然日采集后才能生成有效日环比；周对比仍只在每周结束时生成。

## 验收结论

本次正式运行证明：API 就绪等待修复已在 Ubuntu 的真实 09:00 timer 中生效，采集、ETL、报告生成和 Telegram 图文发送均正常完成，并且没有重复投递。

本次验收不等于已经达到生产级高可用。仍需继续观察连续自然日趋势、周末周对比、登录状态失效、备份恢复和长期运行稳定性。
