# 🔧 פתרון בעיות - TherapyCompanion.AI

## ⚡ פתרון מהיר - משתמש בדיקה

אם יש לך בעיה עם הרישום, צור משתמש בדיקה:

```bash
cd /home/user/VirtualTherapist
source venv/bin/activate
python create_test_user.py
```

**פרטי התחברות:**
- 📧 Email: `test@therapy.ai`
- 🔑 Password: `test123456`

---

## 🐛 בעיות נפוצות ופתרונות

### 1. שגיאה ברישום - "Email already exists"

**הבעיה:** המייל כבר רשום במערכת

**פתרון:**
- נסה להתחבר עם המייל הזה
- או השתמש במייל אחר
- או השתמש במשתמש הבדיקה למעלה

### 2. שגיאה ברישום - "Could not connect to server"

**הבעיה:** הבקאנד לא רץ

**פתרון:**
```bash
# טרמינל 1 - הפעל את הבקאנד
cd /home/user/VirtualTherapist
./start-backend.sh
```

בדוק שהשרת רץ ב: http://localhost:8000/health

### 3. שגיאה - "Invalid API key"

**הבעיה:** חסר Anthropic API key

**פתרון:**
```bash
# ערוך את קובץ .env
nano .env

# הוסף את המפתח שלך:
ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE
```

### 4. שגיאה - "Database connection failed"

**הבעיה:** בעיה עם מסד הנתונים

**פתרון - השתמש ב-SQLite (פשוט יותר):**
```bash
# ערוך .env
nano .env

# שנה את השורה הזו:
DATABASE_URL=sqlite:///./therapy.db
```

### 5. הממשק לא נטען - "Cannot GET /"

**הבעיה:** הפרונטאנד לא רץ

**פתרון:**
```bash
# טרמינל 2 - הפעל את הפרונטאנד
cd /home/user/VirtualTherapist
./start-frontend.sh
```

גש ל: http://localhost:3000

### 6. שגיאה - "node: command not found"

**הבעיה:** Node.js לא מותקן

**פתרון:**
```bash
# Ubuntu/Debian:
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# או השתמש ב-nvm:
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 18
```

### 7. הממשק בעברית לא נראה נכון

**הבעיה:** בעיה עם RTL

**פתרון:**
- רענן את הדפדפן (Ctrl+Shift+R)
- נקה cache של הדפדפן
- נסה דפדפן אחר (Chrome, Firefox)

### 8. שגיאה - "Port 8000 already in use"

**הבעיה:** הפורט תפוס

**פתרון:**
```bash
# מצא את התהליך ועצור אותו
lsof -i :8000
kill -9 <PID>

# או שנה את הפורט בקובץ app/main.py:
uvicorn.run("app.main:app", host="0.0.0.0", port=8001)
```

---

## ✅ בדיקה שהכל עובד

### 1. בדוק שהבקאנד רץ:
```bash
curl http://localhost:8000/health
```

אמור להחזיר:
```json
{
  "status": "healthy",
  "app": "TherapyCompanion.AI",
  "version": "1.0.0"
}
```

### 2. בדוק שהפרונטאנד רץ:

פתח בדפדפן: http://localhost:3000

אמור לראות את עמוד ההתחברות

### 3. התחבר עם משתמש הבדיקה:

- Email: `test@therapy.ai`
- Password: `test123456`

---

## 🆘 עדיין לא עובד?

### אפס הכל והתחל מחדש:

```bash
cd /home/user/VirtualTherapist

# 1. עצור את כל השרתים (Ctrl+C)

# 2. מחק את מסד הנתונים
rm -f therapy.db

# 3. צור משתמש בדיקה מחדש
source venv/bin/activate
python create_test_user.py

# 4. הפעל את הבקאנד (טרמינל 1)
./start-backend.sh

# 5. הפעל את הפרונטאנד (טרמינל 2)
./start-frontend.sh

# 6. גש ל http://localhost:3000
```

---

## 📋 רשימת בדיקות

- [ ] Python 3.11+ מותקן (`python3 --version`)
- [ ] Node.js 18+ מותקן (`node --version`)
- [ ] קובץ .env קיים עם API key
- [ ] הבקאנד רץ על פורט 8000
- [ ] הפרונטאנד רץ על פורט 3000
- [ ] יש חיבור לאינטרנט (לשימוש ב-AI)
- [ ] הדפדפן תומך ב-RTL (כל הדפדפנים המודרניים)

---

## 💡 טיפים

1. **תמיד הפעל את הבקאנד לפני הפרונטאנד**
2. **השתמש בשני טרמינלים נפרדים**
3. **בדוק את הקונסול בדפדפן (F12) לשגיאות**
4. **SQLite פשוט יותר מ-PostgreSQL לבדיקות**
5. **אם יש שגיאה - רענן את הדף**

---

## 📞 לוגים מועילים

### לוגים של הבקאנד:
```bash
# בטרמינל שבו רץ הבקאנד, תראה:
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### לוגים של הפרונטאנד:
```bash
# בטרמינל שבו רץ הפרונטאנד:
VITE v5.0.11  ready in 523 ms

➜  Local:   http://localhost:3000/
➜  Network: use --host to expose
```

---

**אם כלום לא עובד - תן לי לדעת איזו שגיאה מופיעה ואני אעזור!** 🚀
