$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$script = Join-Path $root 'scripts\download-wechat-article.ps1'
$launcher = Join-Path $root 'scripts\download-wechat-article.cmd'

$tokens = $null
$parseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile($script, [ref]$tokens, [ref]$parseErrors) | Out-Null
if ($parseErrors.Count -ne 0) { throw "PowerShell 语法错误：$($parseErrors[0].Message)" }

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) "jobflow-download-test-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
try {
    $invalidFailed = $false
    try {
        & $script -Date '2026-02-31' -ServerUser test -ServerHost example.invalid -RemoteRoot /srv/jobflow -OutputRoot $tempRoot -SkipOpen
    }
    catch { $invalidFailed = $_.Exception.Message -like '*日期无效*' }
    if (-not $invalidFailed) { throw '无效日期没有被拒绝。' }

    $existing = Join-Path $tempRoot 'wechat-2026-08-28'
    New-Item -ItemType Directory -Force -Path $existing | Out-Null
    $marker = Join-Path $existing 'keep.txt'
    Set-Content -LiteralPath $marker -Value 'keep' -Encoding UTF8
    $existingFailed = $false
    try {
        & $script -Date '2026-08-28' -ServerUser test -ServerHost example.invalid -RemoteRoot /srv/jobflow -OutputRoot $tempRoot -SkipOpen
    }
    catch { $existingFailed = $_.Exception.Message -like '*目标目录已存在*' }
    if (-not $existingFailed) { throw '已有目录没有触发覆盖保护。' }
    if (-not (Test-Path -LiteralPath $marker)) { throw '覆盖保护删除了已有文件。' }

    $source = Get-Content -LiteralPath $script -Raw -Encoding UTF8
    foreach ($required in @('article.md', 'article.html', 'cover.png', 'manifest.json', 'trend.png', 'new_job_count')) {
        if (-not $source.Contains($required)) { throw "脚本缺少校验标记：$required" }
    }
    $launcherSource = Get-Content -LiteralPath $launcher -Raw
    if (-not $launcherSource.Contains('download-wechat-article.ps1')) { throw 'CMD 启动器没有调用 PowerShell 脚本。' }
    if (-not $launcherSource.Contains('ExecutionPolicy Bypass')) { throw 'CMD 启动器没有处理脚本执行策略。' }
    Write-Host 'download-wechat-article tests passed'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
