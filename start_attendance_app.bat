@echo off
set "APP_DIR=%~dp0"

REM Prefer a local venv if present
if exist "%APP_DIR%.venv\Scripts\python.exe" (
  set "PYTHON_EXE=%APP_DIR%.venv\Scripts\python.exe"
) else (
  REM Fall back to system python on PATH
  for %%P in (python.exe python3.exe) do if exist "%%~$PATH:P" set "PYTHON_EXE=%%~$PATH:P" & goto :gotpython
)

if not defined PYTHON_EXE (
  echo Python was not found on PATH and no .venv exists.
  echo Run `setup_env.ps1` to create a virtual environment.
  pause
  exit /b 1
)

:gotpython
"%PYTHON_EXE%" "%APP_DIR%attendance_app.py"
