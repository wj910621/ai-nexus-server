# Nexus AI Studio - Full Dev Environment
# Starts both the backend and frontend server

Write-Host "=== Nexus AI Studio Developer Environment ===" -ForegroundColor Cyan
Write-Host "`nThis script will start both servers in separate windows.`n" -ForegroundColor Gray

# Start backend
$backendScript = Join-Path $PSScriptRoot "server" "start-backend.ps1"
if (Test-Path $backendScript) {
    Write-Host "Starting backend (localhost:8000)..." -ForegroundColor Yellow
    $backendJob = Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$backendScript'" -PassThru -WindowStyle Normal
    Start-Sleep 2
}

# Serve frontend at localhost:3000
Write-Host "Starting frontend (localhost:3000)..." -ForegroundColor Yellow
$frontendJob = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; python -m http.server 3000" -PassThru -WindowStyle Normal

Write-Host "`n=== Services ===" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Green
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "`nPress any key to stop all servers..." -ForegroundColor Gray

$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Cleanup
if ($backendJob -and !$backendJob.HasExited) { $backendJob.Kill() }
if ($frontendJob -and !$frontendJob.HasExited) { $frontendJob.Kill() }

Write-Host "Servers stopped." -ForegroundColor Yellow
