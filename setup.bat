@echo off
chcp 65001 >nul
echo ============================================
echo   智能文书编写系统 - 环境安装
echo ============================================
echo.

cd /d "%~dp0"

echo [1/2] 安装 Python 依赖...
cd backend
pip install -r requirements.txt
cd ..

echo.
echo [2/2] 配置环境变量...
if not exist "backend\.env" (
    echo # 请填入你的 API 配置 > backend\.env
    echo OPENAI_API_KEY=your_api_key_here >> backend\.env
    echo OPENAI_BASE_URL=https://api.openai.com/v1 >> backend\.env
    echo MODEL_NAME=gpt-4o >> backend\.env
    echo 已创建 backend\.env，请编辑填入 API 配置
) else (
    echo backend\.env 已存在，跳过
)

echo.
echo ============================================
echo   安装完成！运行 run.bat 启动系统
echo ============================================
pause
