@echo off
chcp 65001 >nul
REM MemCore Standalone Server Starter (CMD/Batch version)
REM Usage: start-memcore.bat [port] [host]

setlocal enabledelayedexpansion

REM Default values
set "PORT=8080"
set "HOST=127.0.0.1"

REM Parse arguments
if not "%~1"=="" set "PORT=%~1"
if not "%~2"=="" set "HOST=%~2"

REM Get script directory
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Check for uv
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 'uv' is not installed or not in PATH
    echo Please install from: https://github.com/astral-sh/uv
    exit /b 1
)

REM Check for .env
if not exist ".env" (
    echo [WARNING] .env file not found
    echo Please copy .env.example to .env and configure your API keys
)

REM Create data directories if needed
if not exist "dataCrystal" mkdir "dataCrystal"
if not exist "dataCrystal\logs" mkdir "dataCrystal\logs"

REM Display startup info
echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║                    MemCore Standalone Server                   ║
echo ║                    Agentic Memory Management                   ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.
echo [INFO] Starting MemCore server...
echo        Mode:      SSE (Server-Sent Events)
echo        Host:      %HOST%
echo        Port:      %PORT%
echo        Log:       dataCrystal/logs/memcore.log
echo.
echo Press Ctrl+C to stop the server
echo.

REM Check if venv exists, if not run sync
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Running uv sync first...
    uv sync --extra sse
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies
        exit /b 1
    )
)

REM Set PYTHONPATH for imports
set "PYTHONPATH=%SCRIPT_DIR%"

REM Run the server
.venv\Scripts\python.exe src\memcore\main.py --mode sse --host %HOST% --port %PORT%

echo.
echo [INFO] MemCore server stopped
pause
