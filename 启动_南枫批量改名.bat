@echo off
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"
where pythonw.exe >nul 2>nul
if errorlevel 1 (
  echo Python is not available. Install Python with PySide6 first.
  pause
  exit /b 1
)
python.exe -c "import PySide6" >nul 2>nul
if errorlevel 1 (
  echo PySide6 is not available in the selected Python environment.
  pause
  exit /b 1
)
start "" pythonw.exe "%APP_DIR%run_silent.pyw"
exit /b 0
