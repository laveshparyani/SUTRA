# Registers the SUTRA edge node to start at logon — no administrator rights.
#
# Creates a shortcut in the user's Startup folder that launches the edge
# runner hidden. Use this when Task Scheduler registration is blocked by
# policy (install_edge_task.ps1 is the elevated equivalent).
#
#     powershell -ExecutionPolicy Bypass -File infra\install_edge_startup.ps1
#
# Remove by deleting the shortcut from:  shell:startup

$ErrorActionPreference = "Stop"
$runner   = Join-Path $PSScriptRoot "run_edge.ps1"
$startup  = [Environment]::GetFolderPath("Startup")
$lnkPath  = Join-Path $startup "SUTRA Edge Node.lnk"

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath  = "powershell.exe"
$lnk.Arguments   = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runner`""
$lnk.WorkingDirectory = Split-Path -Parent $PSScriptRoot
$lnk.WindowStyle = 7          # minimised
$lnk.Description = "SUTRA edge node: CCTV ingest, ANPR, metadata sync"
$lnk.Save()

Write-Host "Installed startup entry: $lnkPath"
Write-Host "Starts automatically at next logon."
Write-Host "Start it now:  powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runner`""
Write-Host "Logs:          data\logs\edge.log"
