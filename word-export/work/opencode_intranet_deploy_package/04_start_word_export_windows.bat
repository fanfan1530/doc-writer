@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

call "%~dp0\01_prepare_runtime_windows.bat"
if errorlevel 1 (
  echo Runtime prepare failed.
  pause
  exit /b 1
)

set PORT=8123
if not "%WORD_EXPORT_PORT%"=="" set PORT=%WORD_EXPORT_PORT%

set SERVICE_IP=
if exist "%~dp0service_ip.txt" set /p SERVICE_IP=<"%~dp0service_ip.txt"

if "%WORD_EXPORT_PUBLIC_BASE_URL%"=="" (
  if "%SERVICE_IP%"=="" (
    set WORD_EXPORT_PUBLIC_BASE_URL=http://127.0.0.1:%PORT%
  ) else (
    set WORD_EXPORT_PUBLIC_BASE_URL=http://%SERVICE_IP%:%PORT%
  )
)

set WORD_EXPORT_PORT=%PORT%
set WORD_EXPORT_TEMPLATE=%~dp0service\templates\reference_layout.docx
set WORD_EXPORT_CHECK_TEMPLATE=%~dp0service\templates\check_record_template.docx
set WORD_EXPORT_IDENTIFICATION_TEMPLATE=%~dp0service\templates\identification_record_template.docx
set WORD_EXPORT_CRIMINAL_RECORD_TEMPLATE=%~dp0service\templates\criminal_record_template.docx
set WORD_EXPORT_ENTRY_MATERIALS_TEMPLATE_DIR=%~dp0service\templates\entry_materials_docx_templates
set WORD_EXPORT_OUTPUT_DIR=%~dp0outputs\word_exports

if not exist "%WORD_EXPORT_OUTPUT_DIR%" mkdir "%WORD_EXPORT_OUTPUT_DIR%"

echo.
echo Word 导出服务启动中...
echo Public URL: %WORD_EXPORT_PUBLIC_BASE_URL%
echo Health:     %WORD_EXPORT_PUBLIC_BASE_URL%/health
echo.
echo 请保持本窗口运行。关闭窗口后，Dify 将不能导出 Word。
echo.

"%~dp0runtime\python-3.12.10-embed-amd64\python.exe" "%~dp0service\word_export_service.py"
pause
