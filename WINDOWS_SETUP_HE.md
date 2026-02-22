# 🪟 הדרכת התקנה ל-Windows

## 📋 דרישות מקדימות

1. **Python 3.11+**
   - הורד מ: https://www.python.org/downloads/
   - ✅ סמן "Add Python to PATH" בהתקנה!

2. **Node.js 18+**
   - הורד מ: https://nodejs.org/
   - בחר ב-LTS version

3. **Git** (אופציונלי)
   - הורד מ: https://git-scm.com/download/win

---

## 🚀 התקנה מהירה

### שלב 1: פתח Command Prompt או PowerShell

לחץ `Win + R`, הקלד `cmd`, לחץ Enter

### שלב 2: נווט לתיקיית הפרויקט

```cmd
cd C:\Users\YourName\VirtualTherapist
```

(שנה את הנתיב לפי המיקום שלך)

### שלב 3: הפעל Backend (חלון 1)

```cmd
start-backend.bat
```

הסקריפט יבצע:
- ✅ יצור סביבה וירטואלית
- ✅ יתקין תלויות
- ✅ ייצור מפתחות אבטחה
- ✅ יפעיל את השרת

**אם זו הפעם הראשונה:**
1. הסקריפט ייצור קובץ `.env`
2. פתח את `.env` בעורך טקסט (Notepad)
3. הוסף את ה-API key שלך:
   ```
   ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE
   ```
4. העתק את המפתחות שנוצרו (SECRET_KEY ו-ENCRYPTION_KEY)
5. הרץ שוב: `start-backend.bat`

### שלב 4: צור משתמש בדיקה (חלון 2)

פתח חלון CMD חדש:

```cmd
cd C:\Users\YourName\VirtualTherapist
create-test-user.bat
```

**פרטי התחברות:**
- 📧 Email: `test@therapy.ai`
- 🔑 Password: `test123456`

### שלב 5: הפעל Frontend (חלון 3)

פתח חלון CMD שלישי:

```cmd
cd C:\Users\YourName\VirtualTherapist
start-frontend.bat
```

### שלב 6: פתח בדפדפן

גש ל: **http://localhost:3000**

התחבר עם הפרטים למעלה! ✨

---

## 🎯 דרך מהירה - כל הפקודות ביחד

**CMD חלון 1 (Backend):**
```cmd
cd C:\Users\YourName\VirtualTherapist
start-backend.bat
```

**CMD חלון 2 (יצירת משתמש):**
```cmd
cd C:\Users\YourName\VirtualTherapist
create-test-user.bat
```

**CMD חלון 3 (Frontend):**
```cmd
cd C:\Users\YourName\VirtualTherapist
start-frontend.bat
```

**דפדפן:**
```
http://localhost:3000
```

---

## 🔧 פתרון בעיות ב-Windows

### ❌ "python is not recognized"

**פתרון:**
1. התקן Python מ: https://www.python.org/downloads/
2. ✅ סמן "Add Python to PATH"
3. אתחל את ה-CMD
4. בדוק: `python --version`

### ❌ "npm is not recognized"

**פתרון:**
1. התקן Node.js מ: https://nodejs.org/
2. אתחל את ה-CMD
3. בדוק: `node --version`

### ❌ "Access is denied" בעת התקנת חבילות

**פתרון:**
הרץ CMD כמנהל (Run as Administrator):
1. חפש "cmd" בתפריט התחל
2. לחץ ימני → "Run as administrator"

### ❌ "Port 8000 is already in use"

**פתרון:**
```cmd
REM מצא את התהליך התופס את הפורט
netstat -ano | findstr :8000

REM עצור את התהליך (שנה PID בהתאם)
taskkill /PID 1234 /F
```

### ❌ הממשק לא נטען

**פתרון:**
1. וודא ש-Backend רץ (חלון 1)
2. וודא ש-Frontend רץ (חלון 3)
3. בדוק: http://localhost:8000/health
4. בדוק: http://localhost:3000

### ❌ שגיאות בעברית לא מוצגות נכון

**פתרון:**
```cmd
REM שנה encoding של CMD
chcp 65001
```

---

## 💡 טיפים ל-Windows

### 1. פתח 3 חלונות CMD מראש

```cmd
REM בחלון CMD הראשון:
start cmd /k "cd C:\Users\YourName\VirtualTherapist"
start cmd /k "cd C:\Users\YourName\VirtualTherapist"
```

### 2. צור קיצור דרך לשולחן העבודה

1. לחץ ימני על `start-backend.bat`
2. "Send to" → "Desktop (create shortcut)"
3. חזור על זה ל-`start-frontend.bat`

### 3. השתמש ב-Windows Terminal (מומלץ!)

הורד מ-Microsoft Store: "Windows Terminal"
- תמיכה טובה יותר ב-Unicode
- צבעים
- טאבים

---

## 📁 מבנה תיקיות ב-Windows

```
C:\Users\YourName\VirtualTherapist\
│
├── venv\                    # סביבה וירטואלית
├── frontend\                # קוד Frontend
│   └── node_modules\        # תלויות Node
├── app\                     # קוד Backend
├── .env                     # הגדרות (צור ידנית)
├── start-backend.bat        # הפעלת Backend
├── start-frontend.bat       # הפעלת Frontend
└── create-test-user.bat     # יצירת משתמש בדיקה
```

---

## ⚙️ עריכת קובץ .env ב-Windows

### אופציה 1: Notepad
```cmd
notepad .env
```

### אופציה 2: VS Code (אם מותקן)
```cmd
code .env
```

### אופציה 3: כל עורך טקסט אחר

**תוכן דוגמה:**
```env
# מפתחות (השתמש באלו שנוצרו בסקריפט)
SECRET_KEY=YOUR-GENERATED-SECRET-KEY
ENCRYPTION_KEY=YOUR-GENERATED-ENCRYPTION-KEY

# API Key (קבל מ-Anthropic)
ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE

# מסד נתונים (SQLite פשוט ל-Windows)
DATABASE_URL=sqlite:///./therapy.db

# Redis (אופציונלי - אפשר להשמיט)
REDIS_URL=redis://localhost:6379/0
```

---

## 🎨 PowerShell במקום CMD (אופציונלי)

אם אתה מעדיף PowerShell:

```powershell
# הפעל Backend
.\start-backend.bat

# הפעל Frontend
.\start-frontend.bat

# צור משתמש
.\create-test-user.bat
```

---

## 🔒 מסד נתונים ב-Windows

**מומלץ: SQLite** (פשוט, לא צריך התקנה)

בקובץ `.env`:
```env
DATABASE_URL=sqlite:///./therapy.db
```

**אופציונלי: PostgreSQL**

1. הורד מ: https://www.postgresql.org/download/windows/
2. התקן
3. צור מסד נתונים:
   ```cmd
   psql -U postgres
   CREATE DATABASE virtual_therapist;
   ```
4. עדכן ב-`.env`:
   ```env
   DATABASE_URL=postgresql://postgres:password@localhost:5432/virtual_therapist
   ```

---

## ✅ בדיקה שהכל עובד

### 1. בדוק Python
```cmd
python --version
```
אמור להציג: `Python 3.11.x` או גבוה יותר

### 2. בדוק Node
```cmd
node --version
```
אמור להציג: `v18.x.x` או גבוה יותר

### 3. בדוק Backend
```cmd
curl http://localhost:8000/health
```
או פתח בדפדפן: http://localhost:8000/health

### 4. בדוק Frontend
פתח בדפדפן: http://localhost:3000

---

## 🆘 עזרה נוספת

אם משהו לא עובד:
1. בדוק את `TROUBLESHOOTING_HE.md`
2. וודא ש-Python ו-Node בגרסאות הנכונות
3. הרץ CMD כמנהל
4. בדוק את הלוגים בחלונות ה-CMD
5. שאל אותי! 😊

---

## 🎯 סיכום מהיר

```cmd
REM 1. פתח 3 חלונות CMD

REM חלון 1 - Backend
cd C:\Users\YourName\VirtualTherapist
start-backend.bat

REM חלון 2 - יצירת משתמש (פעם אחת)
cd C:\Users\YourName\VirtualTherapist
create-test-user.bat

REM חלון 3 - Frontend
cd C:\Users\YourName\VirtualTherapist
start-frontend.bat

REM דפדפן
http://localhost:3000
תתחבר: test@therapy.ai / test123456
```

**זהו! המערכת אמורה לעבוד! 🚀**
