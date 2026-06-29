@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo 将创建 Windows 计划任务：DifyWordExport
echo 该任务会在当前用户登录时自动启动 Word 导出服务。
echo 如提示权限不足，请右键本文件，选择“以管理员身份运行”。
echo.

set START_SCRIPT=%~dp0\04_start_word_export_windows.bat
schtasks /Create /TN "DifyWordExport" /SC ONLOGON /TR "\"%START_SCRIPT%\"" /F

echo.
echo 完成。可以在“任务计划程序”中查看 DifyWordExport。
echo.
pause
