@echo off
REM ========================================
REM TotalSegmentator Tool Launcher (Windows)
REM 雙擊執行 | Double-click to run
REM ========================================
chcp 65001 > nul

cd /d "%~dp0python"
set "UV_EXE=uv"

REM Check if uv is installed
where uv >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
    ) else if exist "%USERPROFILE%\.cargo\bin\uv.exe" (
        set "UV_EXE=%USERPROFILE%\.cargo\bin\uv.exe"
    ) else (
        echo [INFO] uv not installed, installing...
        echo [INFO] uv 尚未安裝，正在安裝...
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        if exist "%USERPROFILE%\.local\bin\uv.exe" (
            set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
        ) else if exist "%USERPROFILE%\.cargo\bin\uv.exe" (
            set "UV_EXE=%USERPROFILE%\.cargo\bin\uv.exe"
        ) else (
            where uv >nul 2>&1
            if %errorlevel% neq 0 (
                echo [ERROR] Failed to install uv or locate uv.exe
                echo [錯誤] uv 安裝失敗，或找不到 uv.exe
                pause
                exit /b 1
            )
        )
    )
)

REM Run gui_pyside.py with uv
"%UV_EXE%" run gui_pyside.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to launch
    echo [錯誤] 啟動失敗
    echo [DEBUG] Current uv command: %UV_EXE%
    pause
)
