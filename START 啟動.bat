@echo off
setlocal

REM Default: launch hidden console to avoid duplicate black cmd window.
REM Debug mode: pass --show-console to keep this window visible.
if /I not "%~1"=="--show-console" (
    if /I not "%~1"=="__hidden__" (
        set "_vbs=%temp%\totalseg_hidden_%random%.vbs"
        >"%_vbs%" echo Set WshShell = CreateObject("WScript.Shell")
        >>"%_vbs%" echo WshShell.Run """" ^& WScript.Arguments(0) ^& """ __hidden__"", 0, False
        cscript //nologo "%_vbs%" "%~f0"
        del "%_vbs%" >nul 2>&1
        exit /b
    )
) else (
    shift
)

if /I "%~1"=="__hidden__" shift

REM ========================================
REM TotalSegmentator Tool Launcher (Windows)
REM 雙擊執行 | Double-click to run
REM ========================================
chcp 65001 > nul

cd /d "%~dp0python"

REM Check if uv is installed
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] uv not installed, installing...
    echo [INFO] uv 尚未安裝，正在安裝...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install uv
        echo [錯誤] uv 安裝失敗
        pause
        exit /b 1
    )
    echo.
    echo [SUCCESS] uv installed! Please close and re-run this file.
    echo [成功] uv 已安裝！請關閉視窗後重新執行此檔案。
    pause
    exit /b 0
)

REM Run gui_pyside.py with uv
uv run gui_pyside.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to launch
    echo [錯誤] 啟動失敗
    pause
)
