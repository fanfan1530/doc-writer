@echo off
chcp 65001 >nul
echo.
echo 本机 IPv4 地址如下。请选择 Dify 服务器可以访问到的固定内网 IP。
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown'} | Select-Object InterfaceAlias,IPAddress | Format-Table -AutoSize"
echo.
pause
