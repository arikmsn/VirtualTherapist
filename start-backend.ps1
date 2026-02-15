# TherapyCompanion.AI - Backend Startup Script (PowerShell)

Write-Host "`n======================================" -ForegroundColor Cyan
Write-Host "  TherapyCompanion.AI - Backend" -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "[!] קובץ .env לא נמצא. יוצר מהתבנית..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "`n[!] אנא ערוך את קובץ .env והוסף:" -ForegroundColor Yellow
    Write-Host "   - ANTHROPIC_API_KEY או OPENAI_API_KEY"
    Write-Host "   - SECRET_KEY"
    Write-Host "   - ENCRYPTION_KEY`n"

    Write-Host "מפתחות אבטחה מוצעים:" -ForegroundColor Green
    python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32)); print('ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"

    Write-Host "`nלאחר עריכת .env, הרץ את הסקריפט שוב." -ForegroundColor Yellow
    Write-Host "או פתח .env ב-VS Code: code .env`n" -ForegroundColor Cyan

    Read-Host "לחץ Enter כדי לצאת"
    exit 1
}

# Check if virtual environment exists
if (-not (Test-Path venv)) {
    Write-Host "[*] יוצר סביבה וירטואלית..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "[*] מפעיל סביבה וירטואלית..." -ForegroundColor Green
& .\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "[*] מתקין תלויות..." -ForegroundColor Green
pip install -q -r requirements.txt

# Start backend
Write-Host "`n======================================" -ForegroundColor Cyan
Write-Host "  מפעיל שרת Backend" -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan
Write-Host "✓ API זמין ב: " -NoNewline -ForegroundColor Green
Write-Host "http://localhost:8000" -ForegroundColor Blue
Write-Host "✓ תיעוד API ב: " -NoNewline -ForegroundColor Green
Write-Host "http://localhost:8000/docs" -ForegroundColor Blue
Write-Host ""

python -m app.main
