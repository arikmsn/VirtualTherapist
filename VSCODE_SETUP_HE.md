# 🎨 מדריך VS Code + PowerShell

## 🚀 התקנה מהירה ב-VS Code

### שלב 1: פתח את הפרויקט ב-VS Code

```powershell
# ב-PowerShell:
cd C:\Users\YourName\VirtualTherapist
code .
```

### שלב 2: אפשר הרצת סקריפטים PowerShell (פעם אחת)

ב-PowerShell **כמנהל** (Run as Administrator):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

לחץ `Y` לאישור.

### שלב 3: הפעל את המערכת

יש לך 3 אפשרויות:

#### אופציה 1: שימוש ב-VS Code Tasks (הכי נוח!)

1. לחץ `Ctrl + Shift + P`
2. הקלד: `Tasks: Run Task`
3. בחר:
   - `🧪 Run All` - מפעיל Backend + Frontend ביחד
   - `🚀 Start Backend` - רק Backend
   - `🎨 Start Frontend` - רק Frontend
   - `👤 Create Test User` - יצירת משתמש בדיקה

#### אופציה 2: Terminal ב-VS Code

פתח Terminal ב-VS Code (`Ctrl + backtick`):

**Terminal 1 (Backend):**
```powershell
.\start-backend.ps1
```

**Terminal 2 (Frontend):**
```powershell
.\start-frontend.ps1
```

**Terminal 3 (משתמש בדיקה - פעם אחת):**
```powershell
.\create-test-user.ps1
```

#### אופציה 3: קיצורי מקלדת (אופציונלי)

צור `.vscode/keybindings.json`:

```json
[
  {
    "key": "ctrl+shift+b",
    "command": "workbench.action.tasks.runTask",
    "args": "🚀 Start Backend"
  },
  {
    "key": "ctrl+shift+f",
    "command": "workbench.action.tasks.runTask",
    "args": "🎨 Start Frontend"
  }
]
```

---

## 🎯 זרימת עבודה מומלצת

### הפעלה ראשונה:

1. **פתח פרויקט:**
   ```powershell
   code C:\Users\YourName\VirtualTherapist
   ```

2. **צור משתמש בדיקה:**
   - `Ctrl + Shift + P` → `Tasks: Run Task` → `👤 Create Test User`

3. **הפעל הכל:**
   - `Ctrl + Shift + P` → `Tasks: Run Task` → `🧪 Run All`

4. **פתח בדפדפן:**
   - http://localhost:3000
   - התחבר: `test@therapy.ai` / `test123456`

### הפעלה רגילה:

1. פתח VS Code
2. `Ctrl + Shift + P` → `Tasks: Run Task` → `🧪 Run All`
3. גש ל-http://localhost:3000

---

## 📦 Extensions מומלצים ל-VS Code

### Python:
- `ms-python.python` - Python
- `ms-python.vscode-pylance` - Pylance
- `ms-python.black-formatter` - Black Formatter

### TypeScript/React:
- `dbaeumer.vscode-eslint` - ESLint
- `esbenp.prettier-vscode` - Prettier

### כלליים:
- `GitHub.copilot` - GitHub Copilot (אופציונלי)
- `eamodio.gitlens` - GitLens
- `ritwickdey.LiveServer` - Live Server

התקנה מהירה:
```powershell
# ב-Terminal של VS Code:
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension dbaeumer.vscode-eslint
code --install-extension esbenp.prettier-vscode
```

---

## 🎨 Structure של VS Code

```
VirtualTherapist/
├── .vscode/
│   ├── tasks.json          # Tasks להרצת Backend/Frontend
│   ├── settings.json       # הגדרות פרויקט
│   └── extensions.json     # Extensions מומלצים
├── app/                    # Backend code
├── frontend/               # Frontend code
├── start-backend.ps1       # PowerShell script
├── start-frontend.ps1      # PowerShell script
└── create-test-user.ps1    # PowerShell script
```

---

## 🔧 פתרון בעיות ב-VS Code

### ❌ "cannot be loaded because running scripts is disabled"

**פתרון:**

פתח PowerShell **כמנהל**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### ❌ Terminal לא פותח ב-PowerShell

**פתרון:**

1. `Ctrl + Shift + P`
2. הקלד: `Terminal: Select Default Profile`
3. בחר: `PowerShell`

### ❌ Python interpreter לא נמצא

**פתרון:**

1. `Ctrl + Shift + P`
2. הקלד: `Python: Select Interpreter`
3. בחר: `.\venv\Scripts\python.exe`

### ❌ Tasks לא פועלים

**פתרון:**

בדוק ש-`tasks.json` קיים ב-`.vscode/tasks.json`

אם לא - הסקריפט יצר אותו אוטומטית.

---

## 💡 טיפים ל-VS Code

### 1. פתח מספר Terminals

- `Ctrl + Shift + backtick` - Terminal חדש
- `Ctrl + backtick` - הצג/הסתר Terminal
- קליק על `+` ב-panel של Terminal

### 2. Split Editor

- `Ctrl + \` - פצל את העורך
- צפה בקוד Backend וב-Frontend בו זמנית

### 3. Command Palette

- `Ctrl + Shift + P` - פתח Command Palette
- גש לכל הפקודות של VS Code

### 4. Quick Open

- `Ctrl + P` - פתיחה מהירה של קבצים
- הקלד שם קובץ וקפוץ ישירות

### 5. Multi-cursor

- `Alt + Click` - הוסף cursor נוסף
- `Ctrl + Alt + Down/Up` - cursors מרובים

### 6. Terminal בצד

1. גרור את ה-Terminal לצד
2. עכשיו יש לך קוד + Terminal זה לצד זה

---

## 🎯 Workflow מומלץ

### Setup (פעם אחת):

```powershell
# 1. פתח פרויקט
code .

# 2. אפשר PowerShell (כמנהל)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# 3. צור .env
Copy-Item .env.example .env
code .env  # ערוך והוסף API keys

# 4. צור משתמש בדיקה
.\create-test-user.ps1
```

### יום-יום:

```powershell
# 1. פתח VS Code
code .

# 2. הרץ Tasks
Ctrl+Shift+P → "Tasks: Run Task" → "🧪 Run All"

# 3. זהו! המערכת רצה
```

---

## 🔥 קיצורי מקלדת שימושיים

| קיצור | פעולה |
|-------|-------|
| `Ctrl + backtick` | פתח/סגור Terminal |
| `Ctrl + Shift + backtick` | Terminal חדש |
| `Ctrl + Shift + P` | Command Palette |
| `Ctrl + P` | Quick Open (קבצים) |
| `Ctrl + B` | הצג/הסתר Sidebar |
| `Ctrl + \` | Split Editor |
| `Ctrl + W` | סגור Tab |
| `Ctrl + Shift + F` | חיפוש בכל הקבצים |
| `F5` | Debug/Run |

---

## 📊 Status Bar

התקן בתחתית של VS Code תראה:

- 🐍 Python Interpreter
- 🔌 Git Branch
- ⚠️ Errors/Warnings
- 📡 Live Server (אם מותקן)

---

## 🎨 Theme מומלץ

```powershell
# התקן Theme יפה:
code --install-extension GitHub.github-vscode-theme
```

בחר Theme:
1. `Ctrl + K, Ctrl + T`
2. בחר: `GitHub Dark Default`

---

## ✅ בדיקה שהכל עובד

### 1. בדוק שה-Tasks עובדים:

1. `Ctrl + Shift + P`
2. הקלד: `Tasks: Run Task`
3. אתה אמור לראות:
   - 🚀 Start Backend
   - 🎨 Start Frontend
   - 👤 Create Test User
   - 🧪 Run All

### 2. הרץ "Run All":

- אמור לפתוח 2 Terminals
- אחד ל-Backend (פורט 8000)
- אחד ל-Frontend (פורט 3000)

### 3. פתח בדפדפן:

http://localhost:3000

---

## 🆘 עזרה נוספת

אם משהו לא עובד:

1. בדוק את ה-Terminal Output ב-VS Code
2. ודא ש-PowerShell בגרסה 5.1+ (`$PSVersionTable.PSVersion`)
3. ודא שהרצת `Set-ExecutionPolicy`
4. נסה לסגור ולפתוח את VS Code מחדש
5. שאל אותי! 😊

---

## 🎯 סיכום מהיר

```powershell
# פתח VS Code
code .

# הרץ הכל (בתוך VS Code)
Ctrl+Shift+P → Tasks: Run Task → 🧪 Run All

# או ב-Terminal:
.\start-backend.ps1    # Terminal 1
.\start-frontend.ps1   # Terminal 2

# דפדפן:
http://localhost:3000
```

**זהו! עכשיו אתה מוכן לעבוד עם VS Code! 🚀**
