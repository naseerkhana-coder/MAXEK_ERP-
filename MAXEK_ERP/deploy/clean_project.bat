@echo off
REM MAXEK ERP — Clean project before WinSCP upload (Windows)
setlocal
cd /d "%~dp0.."
echo Cleaning MAXEK ERP project...

if exist __pycache__ rmdir /s /q __pycache__
if exist src\__pycache__ rmdir /s /q src\__pycache__
for /d /r %%d in (__pycache__) do (
  echo %%d | findstr /i "\\.venv\\" >nul && (rem skip) || (
    echo %%d | findstr /i "\\venv\\" >nul && (rem skip) || rmdir /s /q "%%d" 2>nul
  )
)
for /r %%f in (*.pyc *.pyo) do (
  echo %%f | findstr /i "\\.venv\\" >nul && (rem skip) || (
    echo %%f | findstr /i "\\venv\\" >nul && (rem skip) || del /q "%%f" 2>nul
  )
)
del /s /q *.tmp 2>nul
del /s /q *.bak 2>nul
del /s /q *.old 2>nul
echo Done. Ready for WinSCP upload.
