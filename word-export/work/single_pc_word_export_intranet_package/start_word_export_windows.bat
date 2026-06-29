@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set PORT=8123
if not "%WORD_EXPORT_PORT%"=="" set PORT=%WORD_EXPORT_PORT%

if "%WORD_EXPORT_PUBLIC_BASE_URL%"=="" (
  echo.
  echo [提示] 当前没有设置 WORD_EXPORT_PUBLIC_BASE_URL。
  echo 请把下面命令里的 你的内网电脑IP 改成本机固定内网IP 后再运行：
  echo.
  echo   set WORD_EXPORT_PUBLIC_BASE_URL=http://你的内网电脑IP:%PORT%
  echo   start_word_export_windows.bat
  echo.
  echo 本次先使用 http://127.0.0.1:%PORT% 启动，只适合本机测试。
  echo.
  set WORD_EXPORT_PUBLIC_BASE_URL=http://127.0.0.1:%PORT%
)

set WORD_EXPORT_PORT=%PORT%
set WORD_EXPORT_TEMPLATE=%~dp0templates\reference_layout.docx
set WORD_EXPORT_CHECK_TEMPLATE=%~dp0templates\check_record_template.docx
set WORD_EXPORT_IDENTIFICATION_TEMPLATE=%~dp0templates\identification_record_template.docx
set WORD_EXPORT_CRIMINAL_RECORD_TEMPLATE=%~dp0templates\criminal_record_template.docx
set WORD_EXPORT_ENTRY_MATERIALS_TEMPLATE_DIR=%~dp0templates\entry_materials_docx_templates
set WORD_EXPORT_OUTPUT_DIR=%~dp0outputs\word_exports

if not exist "%WORD_EXPORT_OUTPUT_DIR%" mkdir "%WORD_EXPORT_OUTPUT_DIR%"

echo.
echo Word 导出服务启动中...
echo 访问地址: %WORD_EXPORT_PUBLIC_BASE_URL%
echo 健康检查: %WORD_EXPORT_PUBLIC_BASE_URL%/health
echo.
echo 请保持这个窗口不要关闭。关闭窗口后，Dify 将不能导出 Word。
echo.

py -3 "%~dp0word_export_service.py"
if errorlevel 1 (
  echo.
  echo py -3 启动失败，尝试使用 python 命令...
  python "%~dp0word_export_service.py"
)

pause
