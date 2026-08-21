# 漫剧生成软件 - Windows 开发环境启动脚本
# 用法: .\scripts\dev.ps1

param(
    [switch]$SkipDocker,
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$ROOT = Resolve-Path "$PSScriptRoot\.."

Write-Host "🚀 启动 ComicStudio AI 开发环境..." -ForegroundColor Cyan

# 检查 .env 文件
if (-not (Test-Path "$ROOT\.env")) {
    if (Test-Path "$ROOT\.env.example") {
        Write-Host "📋 复制 .env.example 到 .env" -ForegroundColor Yellow
        Copy-Item "$ROOT\.env.example" "$ROOT\.env"
        Write-Host "⚠️  请编辑 .env 文件填入实际配置后重新运行" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "❌ 未找到 .env 或 .env.example 文件" -ForegroundColor Red
        exit 1
    }
}

# 启动基础设施服务
if (-not $SkipDocker) {
    Write-Host "🐳 启动 Docker 基础设施 (postgres, redis, minio)..." -ForegroundColor Green
    Push-Location "$ROOT\docker"
    docker-compose up -d postgres redis minio
    Pop-Location
    Write-Host "✅ 基础设施已启动" -ForegroundColor Green
}

# 启动后端
if (-not $FrontendOnly) {
    Write-Host "🐍 启动后端服务 (http://localhost:8000)..." -ForegroundColor Green
    $backendJob = Start-Job -ScriptBlock {
        param($root)
        Set-Location "$root\backend"
        if (-not (Test-Path ".venv")) {
            python -m venv .venv
        }
        & ".\.venv\Scripts\Activate.ps1"
        pip install -r requirements.txt --quiet
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    } -ArgumentList $ROOT
}

# 启动前端
if (-not $BackendOnly) {
    Write-Host "⚛️  启动前端服务 (http://localhost:5173)..." -ForegroundColor Green
    $frontendJob = Start-Job -ScriptBlock {
        param($root)
        Set-Location "$root\frontend"
        npm install --silent
        npm run dev
    } -ArgumentList $ROOT
}

Write-Host ""
Write-Host "✨ 开发环境已启动:" -ForegroundColor Cyan
Write-Host "   后端 API:  http://localhost:8000/docs" -ForegroundColor White
Write-Host "   前端 UI:   http://localhost:5173" -ForegroundColor White
Write-Host "   MinIO:     http://localhost:9001" -ForegroundColor White
Write-Host ""
Write-Host "按 Ctrl+C 停止所有服务" -ForegroundColor Yellow

try {
    Wait-Job $backendJob, $frontendJob -Any
} finally {
    Write-Host "🛑 停止服务..." -ForegroundColor Yellow
    if ($backendJob) { Stop-Job $backendJob -ErrorAction SilentlyContinue; Remove-Job $backendJob -ErrorAction SilentlyContinue }
    if ($frontendJob) { Stop-Job $frontendJob -ErrorAction SilentlyContinue; Remove-Job $frontendJob -ErrorAction SilentlyContinue }
}
