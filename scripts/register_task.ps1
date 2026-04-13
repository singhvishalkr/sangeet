# Register Sangeet as a Windows Task Scheduler task
# Runs at user logon and stays running 24/7

$TaskName = "SongAutomation"
$Description = "Smart music automation - plays bhajans, aarti, and chill music on schedule"
$BatPath = "C:\Users\vishal\Documents\Song Automation\scripts\start_automation.bat"
$WorkDir = "C:\Users\vishal\Documents\Song Automation"

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Action = New-ScheduledTaskAction `
    -Execute $BatPath `
    -WorkingDirectory $WorkDir

# Trigger: at user logon
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn

# Trigger: also at a specific time daily as backup (in case logon trigger missed)
$TriggerDaily = New-ScheduledTaskTrigger -Daily -At "07:00AM"

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Days 365) `
    -MultipleInstances IgnoreNew

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger @($TriggerLogon, $TriggerDaily) `
    -Settings $Settings `
    -Principal $Principal `
    -Description $Description

Write-Host ""
Write-Host "Task '$TaskName' registered successfully!" -ForegroundColor Green
Write-Host "It will start automatically at logon and daily at 7:00 AM." -ForegroundColor Cyan
Write-Host ""
Write-Host "To test manually: schtasks /run /tn $TaskName" -ForegroundColor Yellow
Write-Host "To check status: schtasks /query /tn $TaskName" -ForegroundColor Yellow
Write-Host "To remove: schtasks /delete /tn $TaskName /f" -ForegroundColor Yellow
