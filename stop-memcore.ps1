#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Stop the running MemCore server.

.DESCRIPTION
    This script stops the MemCore standalone server that was started
    with start-memcore.ps1.

.PARAMETER Force
    Force kill the process if graceful shutdown fails.

.PARAMETER Help
    Show this help message.

.EXAMPLE
    .\stop-memcore.ps1
    # Stop the MemCore server gracefully

.EXAMPLE
    .\stop-memcore.ps1 -Force
    # Force kill the server

.NOTES
    This script looks for the PID file in data/memcore.pid
#>

[CmdletBinding()]
param(
    [switch]$Force,
    
    [switch]$Help
)

# Show help
if ($Help) {
    Get-Help -Name $MyInvocation.MyCommand.Path -Full
    exit 0
}

# Configuration
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataDir = Join-Path $ProjectRoot "data"
$PidFile = Join-Path $DataDir "memcore.pid"

Write-Host "[>>] Stopping MemCore server..." -ForegroundColor Yellow

# Try to find process by PID file
if (Test-Path $PidFile) {
    $pidContent = Get-Content $PidFile -Raw
    $processId = 0
    
    if ([int]::TryParse($pidContent.Trim(), [ref]$processId)) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        
        if ($process) {
            Write-Host "   Found MemCore process (PID: $processId)" -ForegroundColor Gray
            
            try {
                if ($Force) {
                    Stop-Process -Id $processId -Force
                    Write-Host "[OK] Process force-killed" -ForegroundColor Green
                } else {
                    Stop-Process -Id $processId
                    Write-Host "[OK] Process stopped gracefully" -ForegroundColor Green
                }
            } catch {
                Write-Host "❌ Failed to stop process: $_" -ForegroundColor Red
                exit 1
            }
        } else {
            Write-Host "   Process not running (PID: $processId)" -ForegroundColor Gray
        }
        
        # Remove PID file
        Remove-Item $PidFile -Force
    } else {
        Write-Host "   Invalid PID file, removing..." -ForegroundColor Yellow
        Remove-Item $PidFile -Force
    }
} else {
    # Try to find by process name
    $processes = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*memcore*main.py*" -or $_.CommandLine -like "*run_server.py*"
    }
    
    if ($processes) {
        Write-Host "   Found MemCore process(es):" -ForegroundColor Gray
        foreach ($proc in $processes) {
            Write-Host "     PID: $($proc.Id)" -ForegroundColor Gray
            try {
                if ($Force) {
                    Stop-Process -Id $proc.Id -Force
                } else {
                    Stop-Process -Id $proc.Id
                }
                Write-Host "[OK] Stopped PID $($proc.Id)" -ForegroundColor Green
            } catch {
                Write-Host "❌ Failed to stop PID $($proc.Id): $_" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "   No MemCore process found" -ForegroundColor Gray
    }
}

# Also check port 8080
$connections = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq "Listen" }
if ($connections) {
    Write-Host "   Port 8080 is still in use" -ForegroundColor Yellow
    Write-Host "   You may need to restart your computer or kill the process manually" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[DONE] MemCore server stopped" -ForegroundColor Cyan
