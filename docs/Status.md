# TherapyCompanion.AI — Project Status

## Completed Features

### Phase 1: Foundation
- FastAPI backend with SQLAlchemy ORM, JWT auth, bcrypt passwords
- React 18 + TypeScript + Vite + Tailwind CSS frontend (Hebrew/RTL)
- SQLite fallback for local dev (no Docker required)
- Patient & Session CRUD (full REST API)
- Messages workflow: create → approve/reject → send
- 5-step therapist onboarding flow

### Phase 1+: Hardening
- **API Key Validation** — Startup validates AI keys; warns in dev, blocks in prod. Agent handles missing keys gracefully.
- **Frontend Real API Integration** — All pages (Dashboard, Patients, Sessions, Onboarding, Messages) wired to real backend. No mock data remains.

### AI Session Summaries
- **Backend:** `POST /sessions/{id}/summary/from-text` generates structured JSON summary via AI agent. `GET /sessions/{id}/summary` retrieves it.
- **Frontend:** `SessionDetailPage` — notes textarea, "Generate Summary" button, structured display (topics, interventions, homework, progress, risk, mood).
- **Tests:** 4 passing tests with mocked AI client.

## AI Session Summaries — HOW TO TEST

### Prerequisites
- Backend running (`python -m app.main`)
- Frontend running (`cd frontend && npm run dev`)
- A valid AI API key in `.env` (for actual generation; without it you'll see a 503 error)

### Steps

1. **Register/Login** — Go to `http://localhost:3000/register`, create an account.

2. **Create a patient** — Navigate to "מטופלים" (Patients), click "+", fill in a name, save.

3. **Create a session** — From the Dashboard, create a session for that patient with today's date.

4. **Open session detail** — Navigate to "פגישות" (Sessions), click "צור סיכום" on the session row.

5. **Paste notes** — In the notes textarea, enter something like:
   ```
   המטופל דיווח על שיפור קל בחרדה החברתית. עבדנו על חשיפה הדרגתית למצבים חברתיים.
   הטלנו משימת בית: יומן מחשבות אוטומטיות + תרגול נשימה יומי.
   מצב רוח: חרדתי אך משתף פעולה. ללא סיכון מיוחד.
   ```

6. **Click "צור סיכום AI"** — Loading spinner appears. After a few seconds:
   - Structured summary appears with sections: topics, interventions, homework, progress, mood, risk.
   - Summary is saved to DB.

7. **Verify persistence** — Refresh the page or navigate back to Sessions → the session now shows "יש סיכום". Click "צפה בסיכום" to see it again.

### Without AI Key (dry run)
If no real API key is set, clicking "Generate" shows:
> "AI client not initialized. Set a valid API key in .env for AI_PROVIDER='anthropic'."

CRUD and all other features still work normally.

### API Testing (curl)
```bash
# Register and get token
TOKEN=$(curl -s http://localhost:8000/api/v1/auth/register -X POST \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test1234","full_name":"Dr Test"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create patient + session
curl -s http://localhost:8000/api/v1/patients/ -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"full_name":"Test Patient"}'

curl -s http://localhost:8000/api/v1/sessions/ -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"patient_id":1,"session_date":"2026-02-17"}'

# Generate summary (requires real AI key)
curl -s http://localhost:8000/api/v1/sessions/1/summary/from-text -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"notes":"המטופל דיווח על שיפור..."}'

# Get summary
curl -s http://localhost:8000/api/v1/sessions/1/summary \
  -H "Authorization: Bearer $TOKEN"
```

## In Progress

### Next features
- Therapist edit/approve summary workflow
- Audio upload + Whisper transcription (deferred — requires Python <3.13 or Docker)

## QA Agent Skill

A reusable QA review skill that checks every change before merge.

### How to Invoke

```
/therapycompanion-qa <feature intent>
```

Examples:
```
/therapycompanion-qa AI session summary generation from therapist notes
/therapycompanion-qa Add patient export feature with CSV download
```

### What It Reviews

| Section | Focus |
|---------|-------|
| **UX / Flow** | Loading states, Hebrew text, RTL, minimal clicks for busy therapist |
| **Clinical Meaning** | Maps to real therapy workflow, AI stays advisory, no diagnosis |
| **Security & Privacy** | PHI not in logs, JWT on all endpoints, encryption, no XSS/SQLi |
| **Code Quality** | Domain naming, consistent patterns, no dead code |
| **Tests & Edge Cases** | Missing tests, empty states, AI unavailable, long input |

### Output

Produces a structured report with concrete **Action Items** rated:
- **BLOCK** — Must fix before merge
- **WARN** — Should fix, not a blocker
- **NOTE** — Nice-to-have suggestion

### Skill File Location

`.claude/skills/therapycompanion-qa/SKILL.md`
