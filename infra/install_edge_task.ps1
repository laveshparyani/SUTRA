# Registers the SUTRA edge node as a Windows scheduled task.
#
# Runs hidden at logon, restarts on failure, and keeps running after the
# terminal that installed it is closed. Run once:
#     powershell -ExecutionPolicy Bypass -File infra\install_edge_task.ps1
# Remove with:
#     Unregister-ScheduledTask -TaskName "SUTRA Edge Node" -Confirm:$false

$ErrorActionPreference = "Stop"
$taskName = "SUTRA Edge Node"
$runner   = Join-Path $PSScriptRoot "run_edge.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runner`""

$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)   # never time out: this is a service

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "SUTRA edge node: CCTV ingest, ANPR, and metadata sync to the central tier" | Out-Null

Write-Host "Registered '$taskName' (runs hidden at logon)."
Write-Host "Start it now with:  Start-ScheduledTask -TaskName '$taskName'"
Write-Host "Logs:               data\logs\edge.log"
