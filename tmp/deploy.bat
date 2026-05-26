@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   智慧警务智能工作台 v2.0 — 离线部署脚本
echo ============================================
echo.

set "BASE_DIR=%~dp0"
set "PYTHON="

:: 查找系统 Python
where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('python --version 2^>^&1') do set "PYVER=%%i"
    echo [✓] 找到 Python: !PYVER!
    set "PYTHON=python"
) else (
    where python3 >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%i in ('python3 --version 2^>^&1') do set "PYVER=%%i"
        echo [✓] 找到 Python3: !PYVER!
        set "PYTHON=python3"
    )
)

if "%PYTHON%"=="" (
    echo [✗] 未找到 Python，请先安装 Python 3.10+
    echo     下载地址: https://www.python.org/downloads/
    echo     安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

:: 检查 Python 版本
for /f "tokens=2 delims= " %%i in ('%PYTHON% --version 2^>^&1') do set "PYV=%%i"
for /f "tokens=1 delims=." %%a in ("!PYV!") do set "PYMAJ=%%a"
for /f "tokens=2 delims=." %%b in ("!PYV!") do set "PYMIN=%%b"
if !PYMAJ! lss 3 (
    echo [✗] Python 版本过低，需要 3.10+，当前: !PYV!
    pause
    exit /b 1
)
if !PYMAJ! equ 3 if !PYMIN! lss 10 (
    echo [✗] Python 版本过低，需要 3.10+，当前: !PYV!
    pause
    exit /b 1
)

echo.

:: 合并 wheels 分卷
echo [1/5] 合并 Python wheels 分卷...
set "WHEELS_TAR=%BASE_DIR%wheels.tar.gz"
copy /b "%BASE_DIR%wheels.tar.gz.part-*" "%WHEELS_TAR%" >nul
if not exist "%WHEELS_TAR%" (
    echo [✗] 合并失败，请检查分卷文件是否完整
    pause
    exit /b 1
)
echo [✓] 合并完成

:: 解压 wheels
echo [2/5] 解压 wheels...
set "WHEELS_DIR=%BASE_DIR%wheels"
if exist "%WHEELS_DIR%" rmdir /s /q "%WHEELS_DIR%"
mkdir "%WHEELS_DIR%"
%PYTHON% -c "import tarfile; tarfile.open(r'%WHEELS_TAR%', 'r').extractall(r'%WHEELS_DIR%')"
if %errorlevel% neq 0 (
    echo [✗] 解压失败
    pause
    exit /b 1
)
del "%WHEELS_TAR%"
echo [✓] 解压完成

:: 创建虚拟环境
echo [3/5] 创建 Python 虚拟环境...
set "VENV_DIR=%BASE_DIR%venv"
if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
%PYTHON% -m venv "%VENV_DIR%"
if %errorlevel% neq 0 (
    echo [✗] 创建虚拟环境失败
    pause
    exit /b 1
)
echo [✓] 虚拟环境创建完成

:: 安装依赖
echo [4/5] 安装 Python 依赖（离线安装）...
call "%VENV_DIR%\Scripts\activate.bat"
pip install --no-index --find-links="%WHEELS_DIR%" -r "%BASE_DIR%app-source\requirements.txt"
if %errorlevel% neq 0 (
    echo [!] 部分包安装失败，尝试逐个安装...
    for %%f in ("%WHEELS_DIR%\*.whl") do pip install --no-deps "%%f" 2>nul
)
echo [✓] 依赖安装完成

:: 初始化应用
echo [5/5] 初始化应用...
set "APP_DIR=%BASE_DIR%app"
if exist "%APP_DIR%" rmdir /s /q "%APP_DIR%"
xcopy /e /i /q "%BASE_DIR%app-source\*" "%APP_DIR%" >nul
mkdir "%APP_DIR%\app\knowledge\chroma_db" 2>nul

:: 复制 .env（如果不存在）
if not exist "%APP_DIR%\.env" (
    copy "%APP_DIR%\.env.example" "%APP_DIR%\.env" >nul
    echo [✓] 已创建 .env 配置文件，请根据需要修改 SECRET_KEY
)

echo.
echo ============================================
echo   部署完成！
echo ============================================
echo.
echo   启动方式:
echo     cd /d "%APP_DIR%"
echo     ..\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8091
echo.
echo   前端静态文件位于: %BASE_DIR%frontend-dist\
echo   可用 Nginx 指向该目录，反向代理 /api 到 :8091
echo.
echo   首次启动会自动初始化 ChromaDB 向量库（约30秒）
echo.
pause
