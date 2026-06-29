@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set RUNTIME_DIR=%~dp0runtime\python-3.12.10-embed-amd64
set RUNTIME_ZIP=%~dp0runtime\python-3.12.10-embed-amd64.zip

if exist "%RUNTIME_DIR%\python.exe" (
  echo Python runtime already exists:
  echo %RUNTIME_DIR%\python.exe
  exit /b 0
)

if not exist "%RUNTIME_ZIP%" (
  echo Missing runtime zip:
  echo %RUNTIME_ZIP%
  exit /b 1
)

echo Extracting Python runtime...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%RUNTIME_ZIP%' -DestinationPath '%RUNTIME_DIR%' -Force"

if not exist "%RUNTIME_DIR%\python.exe" (
  echo Python runtime extraction failed.
  exit /b 1
)

echo Python runtime ready:
"%RUNTIME_DIR%\python.exe" --version
exit /b 0
