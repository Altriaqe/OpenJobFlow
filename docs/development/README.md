# 当前开发资料

本目录只保留当前版本仍在开发或等待验收的设计与计划。代码、测试、项目交接和服务器实际输出是完成状态的最终依据。

## 阅读顺序

1. [`../project-handoff.md`](../project-handoff.md)：当前 Git、部署和下一步。
2. [`specs/2026-08-27-v1-3-3-wechat-daily-new-jobs-article-design.md`](specs/2026-08-27-v1-3-3-wechat-daily-new-jobs-article-design.md)：V1.3.3 微信每日新增岗位公告设计。
3. [`plans/2026-08-27-v1-3-3-wechat-daily-new-jobs-article.md`](plans/2026-08-27-v1-3-3-wechat-daily-new-jobs-article.md)：V1.3.3 实施计划。
4. [`plans/2026-08-28-wechat-article-download-script.md`](plans/2026-08-28-wechat-article-download-script.md)：V1.3.4 Windows 一键拉取文章包实施计划。
5. [`specs/2026-08-27-wechat-markdown-job-divider-design.md`](specs/2026-08-27-wechat-markdown-job-divider-design.md)：公众号 Markdown 导入兼容与标准排版设计。
5. [`plans/2026-08-27-wechat-markdown-job-divider.md`](plans/2026-08-27-wechat-markdown-job-divider.md)：公众号 Markdown 标准排版实施计划。
6. [`specs/2026-08-26-wechat-official-daily-delivery-design.md`](specs/2026-08-26-wechat-official-daily-delivery-design.md)：V1.3.2 微信推送设计。
7. [`plans/2026-08-26-wechat-official-daily-delivery.md`](plans/2026-08-26-wechat-official-daily-delivery.md)：V1.3.2 实施计划。
8. [`specs/2026-08-27-wechat-article-package-permissions-design.md`](specs/2026-08-27-wechat-article-package-permissions-design.md)：文章包权限修复设计。
9. [`plans/2026-08-27-wechat-article-package-permissions.md`](plans/2026-08-27-wechat-article-package-permissions.md)：文章包权限修复计划。
10. [`specs/2026-08-27-documentation-reorganization-design.md`](specs/2026-08-27-documentation-reorganization-design.md)：文档目录整理设计。
11. [`plans/2026-08-27-documentation-reorganization.md`](plans/2026-08-27-documentation-reorganization.md)：文档目录整理计划。

## 状态边界

- V1.3.2 微信测试号手动送达和首次正式定时任务已经验收；
- V1.3.3 微信每日新增岗位公告已完成 Ubuntu 真实快照生成、两次正式公众号人工发布和 Telegram 并行送达验收；
- V1.3.4 Windows 一键拉取文章包工具已完成 CMD、Windows PowerShell 5、离线保护和 2026-08-28 真实六文件下载验收，当前尚未提交或推送；
- 正式每日任务继续自动发送 Telegram，但微信侧只生成文章包，不再自动发送测试号模板；
- 计划中的步骤不自动代表已经实现。

历史设计与计划见 [`../archive/README.md`](../archive/README.md)。
