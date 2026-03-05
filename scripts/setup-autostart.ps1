# MemCore Auto-Start Setup Script
# Run this as Administrator to create a Task Scheduler entry

# Check if running as admin
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Must run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

$scriptPath = "E:\workspace\MemCore\start-memcore.ps1"
$taskName = "MemCore"

# Create the action
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`""

# Create the trigger (at log on)
$trigger = New-ScheduledTaskTrigger -AtLogOn

# Create settings (restart on failure, don't stop on battery, etc.)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Create new task
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "MemCore MCP Server - Auto-start on login" `
    -Force

Write-Host ""
Write-Host "Task Scheduler entry created successfully!" -ForegroundColor Green
Write-Host "MemCore will auto-start when you log in." -ForegroundColor Gray
Write-Host ""
Write-Host "Commands:" -ForegroundColor Cyan
Write-Host "  Start now:  schtasks /run /tn MemCore" -ForegroundColor White
Write-Host "  Stop:       schtasks /end /tn MemCore" -ForegroundColor White
Write-Host "  Remove:     schtasks /delete /tn MemCore /f" -ForegroundColor White
Write-Host ""
