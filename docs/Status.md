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

### Session Summary Save, Approve & Per-Patient History
- **Backend:** `PATCH /sessions/{id}/summary` — edit content, save draft, or approve. `GET /patients/{id}/summaries` — per-patient summary history with session metadata.
- **Model:** `SummaryStatus` enum (draft/approved), `status` column on `SessionSummary`.
- **Frontend:** `SessionDetailPage` — editable summary fields (full summary, progress, next plan, mood, risk), "שמור טיוטה" (save draft) and "אשר סיכום" (approve) buttons, status badges. `PatientSummariesPage` — per-patient summary timeline with topic chips.
- **Tests:** 8 passing tests (4 original + 4 new: PATCH edit, PATCH approve, patient summaries list, patient summaries empty).

### Patient Insight Summary
- **Backend:** `POST /patients/{id}/insight-summary` — generates a cross-session AI report from all **approved** summaries. Returns structured JSON: overview, progress, patterns, risks, suggestions for next sessions. Returns 400 if no approved summaries exist, 503 if AI key missing.
- **Agent:** New `generate_patient_insight_summary()` method with dedicated Hebrew prompt. Emphasizes therapist-only use, no diagnosis.
- **Frontend:** `PatientSummariesPage` — purple "סיכום עומק AI" panel with "צור סיכום עומק" button (disabled when 0 approved summaries). Displays structured sections: overview, progress, patterns, risks (amber), suggestions (green). Friendly message when no approved summaries.
- **Tests:** 11 passing tests (3 new: happy path, no approved summaries, draft-only summaries).

## Patient Insight Summary — HOW TO TEST

### Prerequisites
- Backend running (`python -m app.main`)
- Frontend running (`cd frontend && npm run dev`)
- A valid AI API key in `.env`

### Steps

1. **Register/Login** — Go to `http://localhost:3000/register`, create an account.

2. **Create a patient** — Navigate to "מטופלים" (Patients), click "+", fill in a name, save.

3. **Create 2–3 sessions** — From the Dashboard or via API, create sessions for that patient.

4. **Generate summaries** — For each session, navigate to "פגישות" → click "צור סיכום" → paste notes → click "צור סיכום AI".

5. **Approve summaries** — On each session detail page, click "אשר סיכום" to move from draft → approved.

6. **Open patient summaries** — Navigate to "מטופלים", click the patient card. You'll see the summaries timeline with approved badges.

7. **Generate insight** — Click **"צור סיכום עומק"** in the purple panel at the top. A spinner appears. After a few seconds, the AI report appears with sections:
   - סקירה כללית (overview)
   - התקדמות לאורך זמן (progress)
   - דפוסים מרכזיים (patterns)
   - נקודות סיכון למעקב (risks — amber)
   - רעיונות לפגישות הבאות (suggestions — green)

### Edge Cases
- **No approved summaries:** The "צור סיכום עומק" button is disabled. If called via API, returns 400 with "אין סיכומים מאושרים".
- **No AI key:** Returns 503 with clear error.
- **Draft-only summaries:** Button disabled, API returns 400.

### API Testing (curl)
```bash
# Assumes $TOKEN is set (see AI Session Summaries curl section above)

# Generate insight (requires approved summaries + real AI key)
curl -s http://localhost:8000/api/v1/patients/1/insight-summary -X POST \
  -H "Authorization: Bearer $TOKEN"
```

---

## Therapist Workspace — Current Capabilities

### Data Model: Patient → Session → Summary

Every piece of data follows a strict hierarchy:
- **Patient** — who (name, contact, status)
- **Session** — when + with whom (`patient_id`, `session_date`, `start_time`)
- **Summary** — what happened (`session_id` → always tied to a specific session)

A summary can **never** exist without a session. A session can **never** exist without a patient. This is enforced both in the database (foreign keys) and in the UI (there is no "free-floating" summary editor — summaries are always created from within a specific session's workspace).

### How to Create a Patient
1. Navigate to "מטופלים" (`/patients`).
2. Click the "+" button.
3. Fill in name (required) and optional fields (phone, email, concerns).
4. Click "צור מטופל".

### How to Create a Session for a Patient
1. Via API: `POST /api/v1/sessions/` with `{ patient_id, session_date, start_time }`.
2. The session appears in the daily view and in the sessions list.

### How to Write and Approve a Summary for a Specific Session
1. From the **Dashboard daily view**, click **"פתח סשן"** next to the session.
   - Or from **"פגישות"** (`/sessions`), click **"צור סיכום"** next to a session without a summary.
2. This opens the **SessionDetailPage** (`/sessions/{id}`) — the header clearly shows:
   - Patient name
   - Session date + time + number + type
3. Paste or type session notes into the textarea.
4. Click **"צור סיכום AI"** — the AI generates a structured summary **for THIS session only**.
5. Review the generated summary (topics, interventions, homework, progress, mood, risk).
6. Optionally click **"ערוך סיכום"** to edit, then **"שמור טיוטה"** to save.
7. Click **"אשר סיכום"** to approve — the badge changes from "טיוטה" to "מאושר".

There is no other place in the app to create a summary. The Dashboard's quick-action buttons navigate to the sessions list or patients list — they never open a floating editor.

### Daily View + Session Prep Brief
- **Dashboard daily view** (`/dashboard`) — the top section shows sessions for the selected date. Date navigation with "יום קודם", "יום הבא", "היום" buttons and a native date picker. Each session row shows start time (HH:MM), patient name, session number, summary badge, and two action buttons: "פתח סשן" and "הכנה לפגישה". Defaults to today's date.
- **Quick actions** — the three cards below the daily view navigate to: Sessions list (for summary creation), Message modal (patient messages), and Patients list. No floating summary editors.
- **Prep brief** (`/sessions/{id}?prep=1`) — amber "הכנה לפגישה" panel on the session detail page. Clicking "הכנה לפגישה" from the daily view auto-generates and displays an AI prep brief with: quick overview, recent progress, key points to revisit, watch-out items (red), and session ideas (green). Also available as a toggle button on any session detail page.

### Per-Patient Summaries Timeline
- **Patients page** (`/patients`) — searchable list of all patients, create new patient via modal.
- **Per-patient summaries** (`/patients/{id}/summaries`) — click any patient card to see a timeline of all AI-generated summaries for that patient. Each entry shows session number, date, status badge, topic chips. Clicking an entry navigates to the full session detail.
- **Patient insight summary** — purple panel at the top of the summaries page. "צור סיכום עומק" generates a cross-session AI report from all approved summaries.

### Navigation Flow
- **Sessions page** (`/sessions`) — lists all sessions with filter tabs (all / with summary / without summary). Each row shows patient name, date, and summary status. "צור סיכום" navigates to the detail page for sessions without a summary; "צפה בסיכום" for sessions that already have one.

---

## "Day in the Life" — A Therapist Using TherapyCompanion.AI

**Morning: Prepare for the day**

1. Dr. Levi logs in at `http://localhost:3000/login` and lands on the **Dashboard**. She sees today's sessions in the daily view — times, patient names, and summary status at a glance.

2. She has 3 sessions today. Before her first session with David, she clicks **"הכנה לפגישה"** next to his name. An amber panel appears with an AI-generated prep brief: where they left off, key themes to revisit, and a watch-out about an anxiety spike mentioned last time. She reads it in 30 seconds and feels ready.

**Between sessions: Add a new patient**

3. A new patient was referred. She clicks "מטופלים" in the sidebar, then the "+" button. In the modal she types the patient's name, phone, and primary concerns, then clicks "צור מטופל". The patient appears in the list instantly.

**After a session: Generate an AI summary**

4. Dr. Levi just finished a 50-minute CBT session with Yael. She clicks **"פתח סשן"** from the daily view (or navigates to "פגישות" and clicks "צור סיכום" next to Yael's session row).

5. On the session detail page, she pastes her raw notes from the session into the textarea — observations, interventions she used, homework she assigned, and her clinical impression.

6. She clicks **"צור סיכום AI"**. A spinner appears for a few seconds. The AI returns a structured summary broken into sections: topics discussed, interventions used, homework assigned, patient progress, mood observed, risk assessment, and a full narrative summary.

**Review and approve**

7. She reads through the AI-generated summary. The progress section needs a small correction — she clicks **"ערוך סיכום"**, updates the wording, and clicks **"שמור ואשר"**. The badge changes from "טיוטה" to "מאושר".

**Checking tomorrow's schedule**

8. Before leaving, she clicks "יום הבא" in the daily view to see tomorrow's sessions. She clicks "הכנה לפגישה" for her first morning patient to review the prep brief and plan ahead.

**End of week: Review a patient's history**

9. She navigates to "מטופלים", clicks a patient's card, and sees a timeline of all past session summaries — dates, topic chips, status badges. She clicks **"צור סיכום עומק"** to generate a cross-session AI insight report with patterns, progress, risks, and ideas for upcoming sessions.

**Key principle:** The AI drafts, the therapist decides. Every summary starts as a draft and requires explicit therapist approval. The AI never contacts patients or makes clinical decisions autonomously.

## Auth Flow — Architecture & Regression Checklist

### Architecture
- **Single source of truth:** `AuthProvider` (React Context) in `frontend/src/auth/AuthProvider.tsx`.
- **Token storage:** `localStorage['access_token']` — one key, one place.
- **User metadata:** `localStorage['auth_user']` — non-sensitive display info (name, email).
- **Hook:** `useAuth()` — exposes `isAuthenticated`, `isReady`, `token`, `user`, `login()`, `logout()`.
- **Route guard:** `ProtectedRoute` (`frontend/src/auth/ProtectedRoute.tsx`) — the ONLY place that redirects unauthenticated users to `/login`. Individual pages have zero auth-redirect logic.
- **401 interceptor:** `api.ts` clears `access_token` + `auth_user` from localStorage and hard-redirects to `/login`.

### Regression Checklist
Run this checklist after any change to `App.tsx`, `auth/`, or `api.ts` interceptors:

1. Open `/login` → log in with a valid user → land on `/dashboard` and **stay there**.
2. Refresh `/dashboard` → remain on `/dashboard` (token persists).
3. Navigate to `/patients`, `/sessions`, `/sessions/:id` — all load without redirect.
4. Click "התנתק" (logout) → land on `/login`.
5. Manually navigate to `/dashboard` while logged out → redirected to `/login`.
6. Open `/login` while already logged in → redirected to `/dashboard` (no loop).
7. In DevTools: `localStorage.removeItem('access_token')` → next navigation to any protected route → redirected to `/login`.

### Rules
- No more than one source of truth for auth state (the `AuthContext`).
- All auth redirects go through `ProtectedRoute`, not via scattered `navigate('/login')` calls.
- The only `navigate('/login')` in the codebase is in `Layout.tsx`'s logout handler (after calling `logout()`).

---

## Daily View + Prep Brief — HOW TO TEST

### Prerequisites
- Backend running (`python -m app.main`)
- Frontend running (`cd frontend && npm run dev`)
- A valid AI API key in `.env` (for prep brief generation)

### Steps

1. **Register/Login** — Go to `http://localhost:3000/register`, create an account.

2. **Create a patient** — Navigate to "מטופלים" (Patients), click "+", fill in a name, save.

3. **Create sessions with start_time** — Via API:
   ```bash
   curl -s http://localhost:8000/api/v1/sessions/ -X POST \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"patient_id":1,"session_date":"2026-02-17","start_time":"2026-02-17T10:00:00"}'
   ```

4. **View daily sessions** — On the Dashboard, the "המפגשים של היום" section shows today's sessions with start times and patient names.

5. **Navigate dates** — Click "יום קודם" / "יום הבא" to browse. Click "היום" to return. Use the date picker for specific dates.

6. **Open a session** — Click "פתח סשן" to go to the session detail page.

7. **Generate prep brief** — Click "הכנה לפגישה" from the daily view. The session detail page opens with the amber prep brief panel auto-loading. Requires at least one approved summary for that patient.

### Prep Brief Requirements
- The patient must have **approved** session summaries (generate summaries → approve them first).
- Without approved summaries, the API returns 400.
- Without an AI key, the API returns 503.

---

## In Progress

### Next features
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
