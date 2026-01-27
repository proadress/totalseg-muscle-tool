@echo off
chcp 65001 >nul

echo ======================================================================
echo Medical Image Segmentation Tool - Setup
echo ======================================================================
echo.

setlocal enabledelayedexpansion
set PYTHON_DIR=%~dp0python

cd /d "%PYTHON_DIR%"

REM Step 1: Check/Install uv
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/4] Installing uv...
    powershell -Command "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
    echo ======================================================================
    echo uv has been installed successfully!
    echo Please close this window and run the setup script again.
    echo ======================================================================
    pause
    exit /b 0
)

echo [1/4] uv already installed - continuing setup
echo

REM Step 2: Create venv if needed
if exist ".venv\Scripts\python.exe" (
    echo [2/4] Virtual environment found - skipping creation
) else (
    echo [2/4] Creating virtual environment...
    uv venv .venv
    if %errorlevel% neq 0 (
        echo Error: Failed to create venv
        pause
        exit /b 1
    )
)
echo.

REM Step 3: Sync/install dependencies
echo [3/4] Installing dependencies...
uv sync
if %errorlevel% neq 0 (
    echo Error: Dependency install failed
    pause
    exit /b 1
)
echo [v] Dependencies installed successfully
echo.

REM Step 4: Launch GUI main (and inform about CLI tool)
if exist "gui_main.py" (
    echo [4/4] Launching GUI...
    uv run gui_main.py
) else (
    echo Warning: gui_main.py not found
)
echo.
exit /b 0
