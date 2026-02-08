<<<<<<< Current (Your changes)
=======
# Auto-start script for Trading Bot Server (PowerShell)
# This script starts the server and keeps it running

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Trading Bot Server..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
    Write-Host "Please install Python or add it to PATH" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Start server with uvicorn
Write-Host "Starting uvicorn server..." -ForegroundColor Yellow
Write-Host "Server will be available at: http://localhost:5000" -ForegroundColor Gray
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

# Ensure UTF-8 for Python and console to avoid encoding errors with emojis
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
# Ensure project root is on PYTHONPATH for "src.*" imports
$env:PYTHONPATH = $scriptPath
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

python -m uvicorn webhook_server_fastapi:app --host 0.0.0.0 --port 5000 --reload --app-dir "$scriptPath"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Server exited with error code: $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
>>>>>>> Incoming (Background Agent changes)
