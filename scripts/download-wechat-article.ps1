[CmdletBinding()]
param(
    [string]$Date = (Get-Date -Format 'yyyy-MM-dd'),
    [string]$ServerUser = $env:JOBFLOW_SERVER_USER,
    [string]$ServerHost = $env:JOBFLOW_SERVER_HOST,
    [string]$RemoteRoot = $env:JOBFLOW_REMOTE_ROOT,
    [string]$OutputRoot = (Join-Path (Get-Location) 'downloads'),
    [switch]$SkipOpen
)

$ErrorActionPreference = 'Stop'

function Stop-Script([string]$Message) {
    throw $Message
}

$parsedDate = [DateTime]::MinValue
if (-not [DateTime]::TryParseExact($Date, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None, [ref]$parsedDate)) {
    Stop-Script "日期无效：$Date，请使用真实存在的 yyyy-MM-dd 日期。"
}

$targetDir = Join-Path $OutputRoot "wechat-$Date"
if (Test-Path -LiteralPath $targetDir) {
    Stop-Script "目标目录已存在，为避免覆盖文章而停止：$targetDir"
}

if (-not $ServerUser) { $ServerUser = Read-Host '输入 Ubuntu SSH 用户名' }
if (-not $ServerHost) { $ServerHost = Read-Host '输入 Ubuntu Tailscale 地址或主机名' }
if (-not $RemoteRoot) { $RemoteRoot = Read-Host '输入 JobFlow 远程目录（例如 /home/用户名/services/jobflow）' }
if (-not $ServerUser -or -not $ServerHost -or -not $RemoteRoot) {
    Stop-Script '服务器用户名、主机和远程目录不能为空。'
}
if (-not (Get-Command scp -ErrorAction SilentlyContinue)) {
    Stop-Script '未找到 scp，请先启用 Windows OpenSSH 客户端。'
}

$remoteArticleDir = "$RemoteRoot/runtime/reports/$Date/wechat"
$remote = "$ServerUser@$ServerHost"
$localTemp = Join-Path ([IO.Path]::GetTempPath()) "jobflow-wechat-$Date-$([guid]::NewGuid().ToString('N'))"

New-Item -ItemType Directory -Force -Path $localTemp | Out-Null
try {
    Write-Host "拉取服务器文章包：$Date"
    Write-Host '需要时请在终端输入 SSH 密码；密码不会显示或保存。'
    & scp -r "$remote`:$remoteArticleDir" $localTemp
    if ($LASTEXITCODE -ne 0) {
        Stop-Script "下载失败：服务器可能尚未生成 $Date 的完整文章包，或 SSH 连接失败。"
    }

    $wechatDir = Join-Path $localTemp 'wechat'
    if (-not (Test-Path -LiteralPath $wechatDir -PathType Container)) {
        Stop-Script '下载后未找到 wechat 目录。'
    }

    $fixedFiles = @('article.md', 'article.html', 'cover.png', 'manifest.json', 'trend.png')
    foreach ($name in $fixedFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $wechatDir $name) -PathType Leaf)) {
            Stop-Script "文章包不完整，缺少：$name"
        }
    }

    $importMd = @(Get-ChildItem -LiteralPath $wechatDir -Filter '*.md' -File | Where-Object { $_.Name -ne 'article.md' })
    if ($importMd.Count -ne 1) {
        Stop-Script "公众号导入 Markdown 数量应为 1，实际为 $($importMd.Count)。"
    }

    $expectedImportName = "$Date 每日新增岗位公告.md"
    if ($importMd[0].Name -ne $expectedImportName) {
        Rename-Item -LiteralPath $importMd[0].FullName -NewName $expectedImportName
    }

    $manifestPath = Join-Path $wechatDir 'manifest.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $manifestDate = if ($manifest.report_date) { [string]$manifest.report_date } else { [string]$manifest.snapshot_date }
    if ($manifestDate -ne $Date) {
        Stop-Script "manifest.json 日期为 $manifestDate，与请求日期 $Date 不一致。"
    }
    if ($null -eq $manifest.new_job_count) {
        Stop-Script 'manifest.json 缺少 new_job_count。'
    }

    New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
    Move-Item -LiteralPath $localTemp -Destination $targetDir
    $finalWechatDir = Join-Path $targetDir 'wechat'

    Write-Host "下载完成：$finalWechatDir" -ForegroundColor Green
    Write-Host "新增岗位：$($manifest.new_job_count)"
    Write-Host "公众号导入文件：$expectedImportName"
    Write-Host "建议标题：$Date 每日新增岗位公告"
    Write-Host '作者：JobFlow分析'
    Write-Host '请人工导入、保存草稿、手机预览，确认无误后发布。'
    if (-not $SkipOpen) {
        Start-Process explorer.exe -ArgumentList $finalWechatDir
    }
}
finally {
    if (Test-Path -LiteralPath $localTemp) {
        Remove-Item -LiteralPath $localTemp -Recurse -Force -ErrorAction SilentlyContinue
    }
}
