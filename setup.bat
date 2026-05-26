@echo off
chcp 65001 >nul
echo ============================================
echo   智能文书编写系统 - 环境安装
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] 安装 Python 依赖（离线）...
echo.
echo   安装核心依赖包 (第1部分)...
cd wheels1
for %%f in (*.whl) do pip install "%%f" --no-deps --quiet
cd ..

echo   安装补充依赖包 (第2部分)...
cd wheels2
for %%f in (*.whl) do pip install "%%f" --no-deps --quiet
cd ..

echo   修复依赖关系...
pip install --no-index --find-links=wheels1 --find-links=wheels2 --no-build-isolation ^
  fastapi uvicorn pydantic pydantic-settings openai anthropic httpx ^
  python-docx python-multipart --quiet

echo.
echo [2/3] 检查安装结果...
python -c "import fastapi, openai, anthropic, httpx, docx; print('  ✓ 所有依赖就绪')"

echo.
echo [3/3] 配置环境变量...
if not exist "backend\.env" (
    echo LLM_BASE_URL=你的API地址 > backend\.env
    echo LLM_API_KEY=你的API密钥 >> backend\.env
    echo LLM_MODEL_LARGE=模型名称 >> backend\.env
    echo LLM_MODEL_SMALL=模型名称 >> backend\.env
    echo ALLOWED_ORIGINS=["http://localhost:9090"] >> backend\.env
    echo APP_NAME=智能文书编写系统 >> backend\.env
    echo DEBUG=false >> backend\.env
    echo   ✓ 已创建 backend\.env，请编辑填入 API 配置
) else (
    echo   backend\.env 已存在，跳过
)

echo.
echo ============================================
echo   安装完成！
echo   编辑 backend\.env 填入 API 配置
echo   然后双击 run.bat 启动系统
echo ============================================
pause
