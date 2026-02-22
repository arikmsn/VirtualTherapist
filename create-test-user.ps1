# TherapyCompanion.AI - Create Test User (PowerShell)

Write-Host "`n======================================" -ForegroundColor Cyan
Write-Host "  יצירת משתמש בדיקה" -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan

# Check if virtual environment exists
if (-not (Test-Path venv)) {
    Write-Host "[!] סביבה וירטואלית לא נמצאה." -ForegroundColor Red
    Write-Host "הרץ ראשית: .\start-backend.ps1`n" -ForegroundColor Yellow
    Read-Host "לחץ Enter כדי לצאת"
    exit 1
}

# Activate virtual environment
Write-Host "[*] מפעיל סביבה וירטואלית..." -ForegroundColor Green
& .\venv\Scripts\Activate.ps1

# Run the test user creation script
Write-Host "[*] יוצר משתמש בדיקה...`n" -ForegroundColor Green
python create_test_user.py

Write-Host ""
Read-Host "לחץ Enter כדי לצאת"
