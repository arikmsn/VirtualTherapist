@echo off
echo.
echo ======================================
echo   יצירת משתמש בדיקה
echo ======================================
echo.

REM Activate virtual environment
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [!] סביבה וירטואלית לא נמצאה. מריץ ראשית start-backend.bat
    pause
    exit /b 1
)

REM Run the test user creation script
python create_test_user.py

echo.
pause
