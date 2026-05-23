@echo off
set "PYTHON_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "APP_DIR=%~dp0"

if not exist "%PYTHON_EXE%" (
  echo Python runtime was not found:
  echo %PYTHON_EXE%
  pause
  exit /b 1
)

"%PYTHON_EXE%" "%APP_DIR%attendance_app.py"
