@echo off
chcp 65001 >nul

echo ======================================================================
echo 手動 vs AI 肌肉分割比較工具
echo ======================================================================
echo.

setlocal enabledelayedexpansion
set PYTHON_DIR=%~dp0python

cd /d "%PYTHON_DIR%"

REM Check if venv exists
if not exist ".venv\Scripts\python.exe" (
    echo [錯誤] 找不到虛擬環境
    echo 請先執行「AI肌肉分割.bat」以建立環境
    echo.
    pause
    exit /b 1
)

echo [啟動] 正在開啟比較工具...
echo.
uv run compare_gui.py

exit /b 0
