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

### Patients List + Per-Patient Summaries Timeline
- **Patients page** (`/patients`) — searchable list of all patients, stats (active count, total, missed exercises), create new patient via modal.
- **Per-patient summaries** (`/patients/{id}/summaries`) — click any patient card (or the "סיכומים" button) to see a timeline of all AI-generated summaries for that patient, sorted newest-first. Each entry shows session number, date, status badge (טיוטה / מאושר), topic chips, and a preview of the summary text. Clicking an entry navigates to the full session detail.
- **Patient insight summary** — purple panel at the top of the summaries page. "צור סיכום עומק" button generates a cross-session AI report synthesizing all approved summaries into patterns, progress, risks, and next-session ideas.

### SessionDetail Workspace: Notes → AI Summary → Edit → Approve
- **Session detail** (`/sessions/{id}`) — the therapist's main workspace for a single session:
  1. **Notes input** — paste or type raw session notes into the textarea.
  2. **AI summary generation** — click "צור סיכום AI" to send notes to the AI agent, which returns a structured summary (topics, interventions, homework, progress, next plan, mood, risk assessment).
  3. **Review** — the summary appears in structured cards with a "טיוטה" (draft) badge.
  4. **Edit** — click "ערוך סיכום" to make the full summary, progress, next plan, mood, and risk fields editable inline.
  5. **Save draft** — click "שמור טיוטה" to persist edits without approving.
  6. **Approve** — click "אשר סיכום" (or "שמור ואשר" while editing) to mark the summary as approved. The badge changes to "מאושר" with a green checkmark.

### Navigation Flow
- **Sessions page** (`/sessions`) — lists all sessions with filter tabs (all / with summary / without summary). Each row shows patient name, date, and summary status. "צור סיכום" navigates to the detail page for sessions without a summary; "צפה בסיכום" for sessions that already have one.

---

## "Day in the Life" — A Therapist Using TherapyCompanion.AI

**Morning: Prepare for the day**

1. Dr. Levi logs in at `http://localhost:3000/login` and lands on the **Dashboard**. She sees today's session count, active patients, and pending messages at a glance.

**Between sessions: Add a new patient**

2. A new patient was referred. She clicks "מטופלים" in the sidebar, then the "+" button. In the modal she types the patient's name, phone, and primary concerns, then clicks "צור מטופל". The patient appears in the list instantly.

**After a session: Generate an AI summary**

3. Dr. Levi just finished a 50-minute CBT session with Yael. She navigates to "פגישות" and clicks "צור סיכום" next to Yael's session row.

4. On the session detail page, she pastes her raw notes from the session into the textarea — observations, interventions she used, homework she assigned, and her clinical impression.

5. She clicks **"צור סיכום AI"**. A spinner appears for a few seconds. The AI returns a structured summary broken into sections: topics discussed, interventions used, homework assigned, patient progress, mood observed, risk assessment, and a full narrative summary.

**Review and approve**

6. She reads through the AI-generated summary. The progress section needs a small correction — she clicks **"ערוך סיכום"**, updates the wording, and clicks **"שמור ואשר"**. The badge changes from "טיוטה" to "מאושר".

**End of day: Review a patient's history**

7. Before tomorrow's session with David, she navigates to "מטופלים", clicks David's card, and sees a timeline of all his past session summaries — dates, topic chips, status badges. She clicks the most recent one to refresh her memory on where they left off.

**Key principle:** The AI drafts, the therapist decides. Every summary starts as a draft and requires explicit therapist approval. The AI never contacts patients or makes clinical decisions autonomously.

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
