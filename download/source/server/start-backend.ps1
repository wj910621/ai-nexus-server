# Nexus AI Studio - Backend Startup Script
# Requires Python 3.10+

$ServerDir = Join-Path $PSScriptRoot "server"
$EnvFile = Join-Path $ServerDir ".env"

Write-Host "=== Nexus AI Studio Backend ===" -ForegroundColor Cyan

# Check Python
$py = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Host "Error: Python not found. Install Python 3.10+ first." -ForegroundColor Red
    exit 1
}
Write-Host "Python: $($py.Source)" -ForegroundColor Green

# Create .env if not exists
if (-not (Test-Path $EnvFile)) {
    @"
DATABASE_URL=sqlite+aiosqlite:///./nexus.db
JWT_SECRET=nexus-ai-studio-dev-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
API_BASE_URL=https://j3trisheng.com
"@ | Set-Content $EnvFile -Encoding utf8
    Write-Host "Created .env with SQLite (dev mode)" -ForegroundColor Yellow
}

# Install/upgrade deps
Write-Host "`nInstalling dependencies..." -ForegroundColor Yellow
Push-Location $ServerDir
try {
    pip install -r requirements.txt -q
    Write-Host "Dependencies installed" -ForegroundColor Green
} catch {
    Write-Host "Warning: pip install failed: $_" -ForegroundColor Yellow
}

# Start server
Write-Host "`nStarting server at http://localhost:8000" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Gray
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Pop-Location
