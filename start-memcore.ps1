#!/usr/bin/env pwsh
#Requires -Version 5.1

<#
.SYNOPSIS
    Start MemCore as a standalone HTTP server.

.DESCRIPTION
    This script starts the MemCore memory management system as a persistent
    standalone service. Multiple MCP clients can connect to this server via HTTP.

.PARAMETER Port
    The port number to bind to (default: 8080).

.PARAMETER ListenHost
    The host address to bind to (default: 127.0.0.1).
    Use "0.0.0.0" to allow remote connections.
    (Alias: -Host for convenience)

.PARAMETER Background
    Run the server in the background (detached process).

.PARAMETER LogFile
    Path to the log file (default: dataCrystal/logs/memcore.log).

.PARAMETER Help
    Show this help message.

.EXAMPLE
    .\start-memcore.ps1
    # Start MemCore with default settings (localhost:8080)

.EXAMPLE
    .\start-memcore.ps1 -Port 9000
    # Start MemCore on port 9000

.EXAMPLE
    .\start-memcore.ps1 -ListenHost 0.0.0.0 -Port 8080
    # Allow remote connections

.EXAMPLE
    .\start-memcore.ps1 -Background -LogFile "C:\logs\memcore.log"
    # Run in background with custom log location

.NOTES
    Requires: PowerShell 5.1+ and uv
    MemCore will continue running until manually stopped.
    Data is stored in: dataCrystal/qdrant_storage/ and dataCrystal/memcore_graph.db
#>

[CmdletBinding()]
param(
    [int]$Port = 8080,
    
    [Alias("Host")]
    [string]$ListenHost = "127.0.0.1",
    
    [switch]$Background,
    
    [string]$LogFile = "",
    
    [switch]$Help
)

# Set UTF-8 encoding for proper display of special characters
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

# Show help
if ($Help) {
    Get-Help -Name $MyInvocation.MyCommand.Path -Full
    exit 0
}

# Configuration
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataDir = Join-Path $ProjectRoot "dataCrystal"
$LogDir = Join-Path $DataDir "logs"

# Set default log file if not provided — use timestamped name to avoid file-lock conflicts
if ([string]::IsNullOrEmpty($LogFile)) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $LogFile = Join-Path $LogDir "memcore_$timestamp.log"
    # Keep a stable symlink/copy alias for tooling that expects memcore.log
    $stableLog = Join-Path $LogDir "memcore.log"
}

# Ensure directories exist
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    Write-Host "[+] Created data directory: $DataDir" -ForegroundColor Green
}

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    Write-Host "[+] Created logs directory: $LogDir" -ForegroundColor Green
}

# Check if uv is installed
$uvPath = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvPath) {
    Write-Host "[X] Error: 'uv' is not installed or not in PATH" -ForegroundColor Red
    Write-Host "   Install from: https://github.com/astral-sh/uv" -ForegroundColor Yellow
    exit 1
}

# Check if .env exists
$envFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "[!] Warning: .env file not found" -ForegroundColor Yellow
    Write-Host "   Copy .env.example to .env and configure your API keys" -ForegroundColor Yellow
}

# Check if port is already in use
$portInUse = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "[X] Error: Port $Port is already in use" -ForegroundColor Red
    Write-Host "   Try a different port: .\start-memcore.ps1 -Port 9000" -ForegroundColor Yellow
    exit 1
}

# Check for stale Qdrant lock file
$lockFile = Join-Path $DataDir "qdrant_storage\.lock"
if (Test-Path $lockFile) {
    try {
        # Try to open the lock file exclusively - succeeds if stale, fails if held by another process
        $fileStream = [System.IO.File]::Open($lockFile, "Open", "ReadWrite", "None")
        $fileStream.Close()
        $fileStream.Dispose()

        # If we got here, the lock file is stale (not held by any process)
        Write-Host "[!] Detected stale Qdrant lock file - removing..." -ForegroundColor Yellow
        Remove-Item $lockFile -Force
        Write-Host "[+] Stale lock removed" -ForegroundColor Green
    } catch {
        # File is locked by another process
        Write-Host "[X] Error: Qdrant storage is locked by another running instance" -ForegroundColor Red
        Write-Host "   Lock file: $lockFile" -ForegroundColor Yellow
        Write-Host "   Stop the other MemCore instance before starting a new one." -ForegroundColor Yellow

        # Try to find which process has it open
        $pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
        if ($pythonProcesses) {
            Write-Host "   Running Python processes:" -ForegroundColor Gray
            $pythonProcesses | Select-Object Id, @{N='Memory(MB)';E={[math]::Round($_.WorkingSet/1MB,1)}} | Format-Table -AutoSize | Out-String | Write-Host -ForegroundColor Gray
        }
        exit 1
    }
}

# Kill any existing MemCore instance (handles stale background processes)
$pidFile = Join-Path $DataDir "memcore.pid"
if (Test-Path $pidFile) {
    $pidContent = Get-Content $pidFile -Raw
    $existingPid = 0
    if ([int]::TryParse($pidContent.Trim(), [ref]$existingPid)) {
        $existing = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($existing) {
            Write-Host "[!] Stopping existing MemCore instance (PID: $existingPid)..." -ForegroundColor Yellow
            Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 800
            Write-Host "[+] Previous instance stopped" -ForegroundColor Green
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# Display startup info
Write-Host @"
╔═══════════════════════════════════════════════════════════════╗
║                    MemCore Standalone Server                   ║
║                    Agentic Memory Management                   ║
╚═══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

Write-Host ">> Starting MemCore server..." -ForegroundColor Green
Write-Host "   Mode:      HTTP (streamable-http transport)" -ForegroundColor Gray
Write-Host "   Host:      $ListenHost" -ForegroundColor Gray
Write-Host "   Port:      $Port" -ForegroundColor Gray
Write-Host "   Log:       $LogFile" -ForegroundColor Gray
Write-Host "   Data Dir:  $DataDir" -ForegroundColor Gray
Write-Host ""

# Change to project directory
Set-Location $ProjectRoot

# Build the command
$pythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$mainScript = Join-Path $ProjectRoot "src\memcore\main.py"

# Set PYTHONPATH for imports
$env:PYTHONPATH = $ProjectRoot

# Check if virtual environment exists
if (-not (Test-Path $pythonExe)) {
    Write-Host "[!] Virtual environment not found. Running uv sync first..." -ForegroundColor Yellow
    & uv sync
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X] Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
}

# Function to check health
function Test-MemCoreHealth {
    param([int]$CheckPort)
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$CheckPort/health" -Method GET -TimeoutSec 2 -ErrorAction SilentlyContinue
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

# Run the server
if ($Background) {
    # Run in background
    Write-Host "[*] Starting in background mode..." -ForegroundColor Cyan
    
    $startTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$startTime] MemCore starting (PID: $PID)" | Out-File -FilePath $LogFile -Append
    
    # Set PYTHONPATH for the new process
    $oldPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = $ProjectRoot
    
    # Create separate error log file (Start-Process requires different files for stdout/stderr)
    $errLogFile = $LogFile -replace '\.log$', '.err.log'
    
    $process = Start-Process -FilePath $pythonExe -ArgumentList @(
        $mainScript,
        "--host", $ListenHost,
        "--port", $Port
    ) -WorkingDirectory $ProjectRoot -RedirectStandardOutput $LogFile -RedirectStandardError $errLogFile -WindowStyle Hidden -PassThru

    # Restore original PYTHONPATH
    $env:PYTHONPATH = $oldPythonPath

    Write-Host "[OK] MemCore started in background (PID: $($process.Id))" -ForegroundColor Green
    Write-Host ""
    Write-Host "   Server URL: http://$ListenHost`:$Port" -ForegroundColor Cyan
    Write-Host "   MCP Endpoint: http://$ListenHost`:$Port/mcp" -ForegroundColor Cyan
    Write-Host "   Health Check: http://$ListenHost`:$Port/health" -ForegroundColor Cyan
    Write-Host "   Logs: $LogFile" -ForegroundColor Cyan
    Write-Host "   Errors: $errLogFile" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   To stop: Stop-Process -Id $($process.Id)" -ForegroundColor Yellow
    Write-Host "   To view logs: Get-Content '$LogFile' -Tail 50 -Wait" -ForegroundColor Yellow
    
    # Save PID to file for later reference
    $pidFile = Join-Path $DataDir "memcore.pid"
    $process.Id | Out-File -FilePath $pidFile
    
} else {
    # Run in foreground
    Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
    Write-Host ""
    
    # Create log directory if needed
    $logDirPath = Split-Path -Parent $LogFile
    if (-not (Test-Path $logDirPath)) {
        New-Item -ItemType Directory -Path $logDirPath -Force | Out-Null
    }
    
    # Tee output to both console and log file
    try {
        & $pythonExe $mainScript --host $ListenHost --port $Port 2>&1 | Tee-Object -FilePath $LogFile -Append
    } catch {
        Write-Host "[X] Server stopped unexpectedly" -ForegroundColor Red
        Write-Host "   Error: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "[DONE] MemCore server stopped" -ForegroundColor Cyan
