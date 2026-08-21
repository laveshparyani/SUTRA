# SUTRA edge node — background runner.
#
# Started at logon (see install_edge_startup.ps1) so ingest, ANPR and the
# upstream sync keep running without a console window. Restarts the backend if
# it ever exits, and rotates its own log.
#
# Note: uvicorn writes its normal logging to stderr. Redirecting a native
# command's stderr inline in Windows PowerShell turns every line into an
# ErrorRecord, which would abort this supervisor on the first log line — so the
# backend is launched via Start-Process with file redirection instead.

$root    = Split-Path -Parent $PSScriptRoot
$python  = Join-Path $root ".venv\Scripts\python.exe"
$backend = Join-Path $root "backend"
$logDir  = Join-Path $root "data\logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log    = Join-Path $logDir "edge.log"
$outLog = Join-Path $logDir "edge.out.log"
$errLog = Join-Path $logDir "edge.err.log"

while ($true) {
    # keep logs from growing without bound
    foreach ($f in @($log, $outLog, $errLog)) {
        if ((Test-Path $f) -and ((Get-Item $f).Length -gt 20MB)) { Move-Item $f "$f.1" -Force }
    }

    "[$(Get-Date -Format s)] starting SUTRA edge node" | Add-Content $log
    $p = Start-Process -FilePath $python `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    $p.WaitForExit()
    "[$(Get-Date -Format s)] backend exited (code $($p.ExitCode)); restarting in 15s" | Add-Content $log
    Start-Sleep -Seconds 15
}
