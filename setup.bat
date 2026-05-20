@echo off
echo === BC Camping Bot Setup ===
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download it from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo Creating virtual environment...
python -m venv .venv

echo Installing dependencies...
.venv\Scripts\pip install --upgrade pip -q
.venv\Scripts\pip install -e . -q

echo Installing Playwright browser...
.venv\Scripts\playwright install chromium

echo.
echo === Setup Complete ===
echo To launch: double-click launch.bat
pause
