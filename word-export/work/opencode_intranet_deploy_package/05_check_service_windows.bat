@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set PORT=8123
set SERVICE_IP=
if exist "%~dp0service_ip.txt" set /p SERVICE_IP=<"%~dp0service_ip.txt"
if "%SERVICE_IP%"=="" set SERVICE_IP=127.0.0.1

set URL=http://%SERVICE_IP%:%PORT%/health
if not "%~1"=="" set URL=%~1

echo.
echo Checking: %URL%
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-RestMethod '%URL%' | ConvertTo-Json -Compress } catch { Write-Host $_.Exception.Message; exit 1 }"
echo.
pause
