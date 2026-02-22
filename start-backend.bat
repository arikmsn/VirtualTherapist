@echo off
echo.
echo ======================================
echo   TherapyCompanion.AI - Backend
echo ======================================
echo.

REM Check if .env exists
if not exist .env (
    echo [!] קובץ .env לא נמצא. יוצר מהתבנית...
    copy .env.example .env
    echo.
    echo [!] אנא ערוך את קובץ .env והוסף:
    echo    - ANTHROPIC_API_KEY או OPENAI_API_KEY
    echo    - SECRET_KEY
    echo    - ENCRYPTION_KEY
    echo.
    echo מפתחות אבטחה מוצעים:
    python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32)); print('ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"
    echo.
    echo לאחר עריכת .env, הרץ את הסקריפט שוב.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist venv (
    echo [*] יוצר סביבה וירטואלית...
    python -m venv venv
)

REM Activate virtual environment
echo [*] מפעיל סביבה וירטואלית...
call venv\Scripts\activate.bat

REM Install dependencies
echo [*] מתקין תלויות...
pip install -q -r requirements.txt

REM Start backend
echo.
echo ======================================
echo   מפעיל שרת Backend
echo ======================================
echo.
echo API זמין ב: http://localhost:8000
echo תיעוד API ב: http://localhost:8000/docs
echo.

python -m app.main
