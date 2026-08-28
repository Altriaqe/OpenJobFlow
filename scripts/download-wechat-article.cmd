@echo off
setlocal
pushd "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0download-wechat-article.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
popd
if not "%JOBFLOW_NO_PAUSE%"=="1" pause
exit /b %EXIT_CODE%
