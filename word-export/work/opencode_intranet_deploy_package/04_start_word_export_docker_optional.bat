@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set PORT=8123
set SERVICE_IP=
if exist "%~dp0service_ip.txt" set /p SERVICE_IP=<"%~dp0service_ip.txt"

if "%SERVICE_IP%"=="" (
  echo 请先运行 03_configure_dify_dsl_ip_windows.bat 设置服务电脑 IP。
  pause
  exit /b 1
)

set WORD_EXPORT_PUBLIC_BASE_URL=http://%SERVICE_IP%:%PORT%

docker compose -f docker-compose.optional.yml up -d
if errorlevel 1 (
  echo Docker 启动失败。请改用 04_start_word_export_windows.bat。
  pause
  exit /b 1
)

echo.
echo Docker Word 导出服务已启动：
echo %WORD_EXPORT_PUBLIC_BASE_URL%/health
echo.
pause
