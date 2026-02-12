# start.ps1 - 一键启动 Node.js + FastAPI

Write-Host "=== Robot Console Dashboard (Unified Port 7000) ===" -ForegroundColor Cyan

# 检查 Python
$pythonExe = "http://localhost:7001/index.html"
if (-not (Test-Path $pythonExe)) {
    Write-Host "Virtual environment not found. Creating..." -ForegroundColor Yellow
    python -m venv .venv
}

# 启动 FastAPI（后台）
Write-Host "Starting FastAPI backend on port 7000..." -ForegroundColor Green
$fastapi = Start-Process -FilePath $pythonExe -ArgumentList "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "7000" -PassThru -NoNewWindow
Write-Host "FastAPI PID: $($fastapi.Id)" -ForegroundColor Green

# 等待 FastAPI 启动
Start-Sleep -Seconds 2

# 启动 Node.js（前台，便于观察日志）
Write-Host "Starting Node.js server on port 7000..." -ForegroundColor Green
Write-Host "Open http://localhost:7000 in your browser" -ForegroundColor Cyan
Write-Host "" 

node server.js

# 清理：用户关闭 Node.js 时停止 FastAPI
Write-Host "Stopping FastAPI backend..." -ForegroundColor Yellow
Stop-Process -Id $fastapi.Id -Force -ErrorAction SilentlyContinue
Write-Host "Done." -ForegroundColor Green
