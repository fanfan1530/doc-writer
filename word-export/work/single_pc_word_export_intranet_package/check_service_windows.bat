@echo off
setlocal
chcp 65001 >nul

set URL=%1
if "%URL%"=="" set URL=http://127.0.0.1:8123/health

echo.
echo 正在检查: %URL%
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-RestMethod '%URL%' | ConvertTo-Json -Compress } catch { Write-Host $_.Exception.Message; exit 1 }"
echo.
pause
