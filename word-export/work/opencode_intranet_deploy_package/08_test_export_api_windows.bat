@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set PORT=8123
set SERVICE_IP=
if exist "%~dp0service_ip.txt" set /p SERVICE_IP=<"%~dp0service_ip.txt"
if "%SERVICE_IP%"=="" set SERVICE_IP=127.0.0.1

set URL=http://%SERVICE_IP%:%PORT%/api/export-word

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$body=@{content='前科证明`n`n张三，性别：男 ，出生日期：1999年01月02日，                  身份证件种类及号码：居民身份证450421199901020033，户籍住址：广西藤县藤州镇测试路1号。`n`n经我所民警在全国违法犯罪人员信息资源库、全国在逃人员信息库、全国吸毒人员信息库、广西警务信息综合应用平台和我所档案室查找档案，在本证明出具之日前，未发现张三在本辖区居住期间有违法犯罪记录。`n`n特此证明。`n`n广西藤县公安局埌南派出所`n`n2026年06月12日'; doc_type='前科证明'; filename='api-test-criminal-record.docx'} | ConvertTo-Json -Compress; Invoke-RestMethod -Uri '%URL%' -Method Post -ContentType 'application/json; charset=utf-8' -Body $body | ConvertTo-Json -Compress"

echo.
pause
