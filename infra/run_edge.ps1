# SUTRA edge node — background runner.
#
# Started by Windows Task Scheduler at logon (see install_edge_task.ps1), so
# ingest, ANPR and the upstream sync keep running without a console window.
# Restarts the backend if it ever exits, and rotates its own log.

$ErrorActionPreference = "Stop"
$root    = Split-Path -Parent $PSScriptRoot
$python  = Join-Path $root ".venv\Scripts\python.exe"
$backend = Join-Path $root "backend"
$logDir  = Join-Path $root "data\logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "edge.log"

# keep the log from growing without bound
if ((Test-Path $log) -and ((Get-Item $log).Length -gt 20MB)) {
    Move-Item $log "$log.1" -Force
}

Set-Location $backend
while ($true) {
    "[$(Get-Date -Format s)] starting SUTRA edge node" | Add-Content $log
    & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 *>> $log
    "[$(Get-Date -Format s)] backend exited (code $LASTEXITCODE); restarting in 15s" | Add-Content $log
    Start-Sleep -Seconds 15
}
