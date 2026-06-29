@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set /p TARGET_IP=请输入运行 Word 导出服务这台电脑的内网IP，例如 192.168.1.50：
if "%TARGET_IP%"=="" (
  echo IP不能为空。
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='dify_workflow_内网单机导出服务版.yml'; $text=Get-Content -LiteralPath $p -Raw -Encoding UTF8; $text=$text -replace 'http://内网电脑IP:8123/api/export-word', 'http://%TARGET_IP%:8123/api/export-word'; Set-Content -LiteralPath $p -Value $text -Encoding UTF8"

echo.
echo 已将 Dify DSL 导出地址改为：
echo http://%TARGET_IP%:8123/api/export-word
echo.
echo 现在可以把 dify_workflow_内网单机导出服务版.yml 导入内网 Dify。
echo.
pause
