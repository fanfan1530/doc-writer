@echo off
chcp 65001 >nul
echo ============================================
echo   智能文书编写系统
echo ============================================
echo.
echo   启动后访问: http://localhost:8002
echo   按 Ctrl+C 停止
echo ============================================
echo.

cd /d "%~dp0\backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
pause
