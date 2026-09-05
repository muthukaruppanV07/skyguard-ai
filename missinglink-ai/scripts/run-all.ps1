# MISSINGLINK AI - one-click local run (no Docker)
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\run-all.ps1

$ErrorActionPreference = "Stop"
$scripts = $PSScriptRoot

Write-Host "==> Starting PostgreSQL service..."
Start-Service postgresql-x64-17 -ErrorAction SilentlyContinue

Write-Host "==> Starting backend (Spring Boot, :8080)..."
Start-Process powershell -ArgumentList "-NoExit -ExecutionPolicy Bypass -File `"$scripts\run-backend.ps1`"" -WorkingDirectory (Resolve-Path "$scripts\..\backend\springboot")

Write-Host "==> Starting AI service (FastAPI, :8000)..."
Start-Process powershell -ArgumentList "-NoExit -ExecutionPolicy Bypass -File `"$scripts\run-ai.ps1`"" -WorkingDirectory (Resolve-Path "$scripts\..\ai-service")

Write-Host "==> Starting frontend (Next.js, :3000)..."
Start-Process powershell -ArgumentList "-NoExit -ExecutionPolicy Bypass -File `"$scripts\run-frontend.ps1`"" -WorkingDirectory (Resolve-Path "$scripts\..\frontend")

Write-Host ""
Write-Host "Waiting for services to come up..."
Start-Sleep -Seconds 8

function Wait-Url($url, $name) {
    for ($i = 0; $i -lt 30; $i++) {
        try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 | Out-Null; Write-Host "$name UP at $url"; return }
        catch { Start-Sleep -Seconds 3 }
    }
    Write-Host "$name NOT responding at $url yet - check its window"
}
Wait-Url "http://localhost:3000" "Frontend "
Wait-Url "http://localhost:8080/actuator/health" "Backend  "
Wait-Url "http://localhost:8000/docs" "AI       "

Write-Host ""
Write-Host "Opening browser..."
Start-Process "http://localhost:3000"
Write-Host ""
Write-Host "Login: admin@missinglink.local / Demo123!"
Write-Host "The three service windows will keep running; close them to stop."
