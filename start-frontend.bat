@echo off
echo.
echo ======================================
echo   TherapyCompanion.AI - Frontend
echo ======================================
echo.

cd frontend

REM Check if node_modules exists
if not exist node_modules (
    echo [*] מתקין תלויות Frontend...
    call npm install
)

REM Check if .env exists
if not exist .env (
    echo [*] יוצר קובץ .env...
    copy .env.example .env
)

REM Start frontend
echo.
echo ======================================
echo   מפעיל שרת Frontend
echo ======================================
echo.
echo ממשק אינטרנט זמין ב: http://localhost:3000
echo.

call npm run dev
