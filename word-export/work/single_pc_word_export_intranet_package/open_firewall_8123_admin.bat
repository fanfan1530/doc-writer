@echo off
chcp 65001 >nul
echo.
echo 将放行 Windows 防火墙 TCP 8123 端口。
echo 如果提示权限不足，请右键本文件，选择“以管理员身份运行”。
echo.
netsh advfirewall firewall add rule name="Dify Word Export 8123" dir=in action=allow protocol=TCP localport=8123
echo.
pause
