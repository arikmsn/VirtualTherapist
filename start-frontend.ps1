# TherapyCompanion.AI - Frontend Startup Script (PowerShell)

Write-Host "`n======================================" -ForegroundColor Cyan
Write-Host "  TherapyCompanion.AI - Frontend" -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan

# Navigate to frontend directory
Set-Location frontend

# Check if node_modules exists
if (-not (Test-Path node_modules)) {
    Write-Host "[*] מתקין תלויות Frontend..." -ForegroundColor Yellow
    npm install
}

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "[*] יוצר קובץ .env..." -ForegroundColor Yellow
    Copy-Item .env.example .env
}

# Start frontend
Write-Host "`n======================================" -ForegroundColor Cyan
Write-Host "  מפעיל שרת Frontend" -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan
Write-Host "✓ ממשק אינטרנט זמין ב: " -NoNewline -ForegroundColor Green
Write-Host "http://localhost:3000" -ForegroundColor Blue
Write-Host ""

npm run dev
