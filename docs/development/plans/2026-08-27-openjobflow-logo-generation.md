# OpenJobFlow Logo Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过 HeyRoute `gpt-image-2` 生成一张符合已批准设计的 OpenJobFlow 高清纯图形 Logo。

**Architecture:** 使用 HeyRoute 技能自带的 SSE 客户端发起一次文生图请求，直接将完成事件中的 PNG 保存到公开资产目录。随后以 PNG 文件头校验尺寸和格式，并通过人工目视检查图形、文字、配色、小尺寸识别度与圆形裁切安全区。

**Tech Stack:** HeyRoute Images API、`gpt-image-2`、Python 标准库、PNG

## Global Constraints

- 只生成 1 张首轮成图，尺寸固定为 `2048x2048`，质量固定为 `high`。
- 图内不出现 `OpenJobFlow`、`OJF` 或任何文字、乱码、水印和第三方标志。
- 图形使用三根由低到高排列的圆角数据柱和一条向右上方延伸的橙色趋势线。
- 背景为深海蓝；数据柱依次为蓝、亮青、薄荷绿；橙色只作为焦点色。
- 风格为扁平、几何、简洁、专业，不使用照片质感、复杂 3D、人物、机器人、简历或公文包。
- 主体完整位于中央安全区，必须适配方形与圆形头像裁切。
- 不显示、记录或提交 `HEYROUTE_API_KEY`。
- 未经用户目视批准，不修改 README，不设置平台头像，不提交或推送。

---

### Task 1: HeyRoute 生成前检查

**Files:**
- Read: `<CODEX_HOME>/skills/heyroute-image-gen/scripts/heyroute_image.py`
- Create after generation: `docs/assets/openjobflow-logo.png`

**Interfaces:**
- Consumes: 环境变量 `HEYROUTE_API_KEY` 和 HeyRoute 技能脚本。
- Produces: 不泄露密钥的可执行生成环境。

- [ ] **Step 1: 确认脚本与密钥是否可用**

Run:

```powershell
$script = Join-Path $env:CODEX_HOME 'skills\heyroute-image-gen\scripts\heyroute_image.py'
if (-not (Test-Path -LiteralPath $script)) { throw 'HeyRoute image script is missing' }
if ([string]::IsNullOrWhiteSpace($env:HEYROUTE_API_KEY)) { throw 'HEYROUTE_API_KEY is missing' }
Write-Output 'HeyRoute preflight passed'
```

Expected: 只输出 `HeyRoute preflight passed`，不输出密钥值。

### Task 2: 生成首张 Logo

**Files:**
- Create: `docs/assets/openjobflow-logo.png`

**Interfaces:**
- Consumes: Task 1 的 HeyRoute 环境和下方完整提示词。
- Produces: `docs/assets/openjobflow-logo.png`。

- [ ] **Step 1: 使用批准后的完整提示词生成一张图片**

Run:

```powershell
$script = Join-Path $env:CODEX_HOME 'skills\heyroute-image-gen\scripts\heyroute_image.py'
$prompt = @'
Create a polished square brand icon for an open-source recruitment data intelligence pipeline and lightweight AI data platform. Center a bold, simple symbol on a solid deep ocean navy background: three rounded vertical data bars rising from left to right, colored vivid blue, bright cyan, and mint green. Add one smooth orange trend signal line moving across the bars and clearly rising toward the upper right, expressing job-market demand trends and continuous data flow. Use flat geometric vector-like shapes, crisp clean edges, strong contrast, balanced spacing, and generous safe margins so every element remains intact inside both a square icon and a circular avatar crop. Professional, modern, memorable, minimal, readable at 128 by 128 pixels. No text, no letters, no numbers, no words, no watermark, no border caption, no people, no faces, no robot, no resume, no briefcase, no magnifying glass, no currency symbols, no third-party logos, no photorealism, no mockup scene, no complex 3D, no glassmorphism, no dense texture, no excessive glow.
'@
python $script $prompt --size 2048x2048 --quality high --out 'docs\assets\openjobflow-logo.png'
```

Expected: SSE 依次出现 `started`、若干 `heartbeat`、`completed`、`done`，脚本成功写入 PNG。业务错误必须以失败处理，不能把 HTTP 200 当成生成成功。若服务实际返回的方图小于 2048×2048，使用 Pillow Lanczos 只做等比例尺寸规范化，不再次调用计费接口。

### Task 3: 文件和视觉验收

**Files:**
- Verify: `docs/assets/openjobflow-logo.png`

**Interfaces:**
- Consumes: Task 2 生成的 PNG。
- Produces: 一张已验证但尚未提交的 Logo，或一个明确的单问题迭代意见。

- [ ] **Step 1: 用 PNG 文件头校验格式和尺寸**

Run:

```powershell
python -c "from pathlib import Path; import struct; p=Path(r'docs\assets\openjobflow-logo.png'); d=p.read_bytes(); assert d[:8] == b'\x89PNG\r\n\x1a\n'; w,h=struct.unpack('>II', d[16:24]); assert (w,h)==(2048,2048), (w,h); print(f'PNG verified: {w}x{h}, {len(d)} bytes')"
```

Expected: 输出 `PNG verified: 2048x2048, <bytes> bytes`。

- [ ] **Step 2: 目视检查原图**

使用本地图片查看工具打开 `docs/assets/openjobflow-logo.png`，逐项确认：

```text
三根数据柱由低到高
趋势线明显向右上方
深海蓝、蓝、亮青、薄荷绿、橙配色正确
不存在文字、乱码、水印或第三方图形
无人物、机器人、简历、公文包和写实场景
主体完整处于中央安全区
```

Expected: 所有项目通过；若失败，只记录一个最影响使用的问题，并在下一轮提示词中只修正该问题。

- [ ] **Step 3: 检查工作树边界**

Run:

```powershell
git status --short --branch
git diff --check
```

Expected: 只出现 Logo、设计规格和生成计划等预期文件；不包含 `.env`、Token、真实岗位数据或个人配置。未获得用户明确授权前停止，不执行 Git 提交或推送。
