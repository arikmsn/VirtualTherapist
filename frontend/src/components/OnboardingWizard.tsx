/**
 * First-time data onboarding wizard.
 * Shown once to new therapists who have completed the AI style onboarding
 * but have not yet added any patient data.
 *
 * Steps:
 *  1 — Add first patient
 *  2 — Add second patient (skippable)
 *  3 — Schedule a session
 *  4 — AI session prep reveal
 */

import { useState, useEffect } from 'react'
import { patientsAPI, sessionsAPI, therapistAPI } from '@/lib/api'

interface Props {
  onComplete: () => void
}

interface PatientForm {
  full_name: string
  age: string
  primary_concerns: string
  therapy_approach: string
}

interface SessionForm {
  patient_id: string
  session_datetime: string
  duration_minutes: string
  notes: string
}

interface PrepBrief {
  history_summary: string[]
  last_session: string[]
  tasks_to_check: string[]
  focus_for_today: string[]
  watch_out_for: string[]
}

const emptyPatient = (): PatientForm => ({
  full_name: '',
  age: '',
  primary_concerns: '',
  therapy_approach: 'other',
})

const THERAPY_APPROACHES = [
  { value: 'CBT', label: 'CBT — קוגניטיבי התנהגותי' },
  { value: 'DBT', label: 'DBT — דיאלקטי התנהגותי' },
  { value: 'ACT', label: 'ACT — קבלה ומחויבות' },
  { value: 'psychodynamic', label: 'פסיכודינמי' },
  { value: 'humanistic', label: 'הומניסטי' },
  { value: 'integrative', label: 'אינטגרטיבי' },
  { value: 'other', label: 'כללי / אחר' },
]

const DURATIONS = [
  { value: '45', label: '45 דקות' },
  { value: '50', label: '50 דקות' },
  { value: '60', label: '60 דקות' },
  { value: '90', label: '90 דקות' },
]

// ── Shared input/label styles ────────────────────────────────────────────────
const inputCls =
  'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm ' +
  'placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent'
const labelCls = 'block text-sm font-medium text-gray-300 mb-1.5'

// ── Step dots ─────────────────────────────────────────────────────────────────
function StepDots({ current, total }: { current: number; total: number }) {
  return (
    <div className="flex items-center gap-2 justify-center mb-1">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`rounded-full transition-all ${
            i + 1 < current
              ? 'w-2.5 h-2.5 bg-indigo-500'
              : i + 1 === current
              ? 'w-3 h-3 bg-indigo-400 ring-2 ring-indigo-400/40'
              : 'w-2.5 h-2.5 bg-gray-700'
          }`}
        />
      ))}
    </div>
  )
}

// ── Patient form ──────────────────────────────────────────────────────────────
function PatientFields({
  data,
  onChange,
}: {
  data: PatientForm
  onChange: (f: PatientForm) => void
}) {
  return (
    <div className="space-y-4">
      <div>
        <label className={labelCls}>שם מלא *</label>
        <input
          type="text"
          className={inputCls}
          placeholder="ישראל ישראלי"
          value={data.full_name}
          onChange={(e) => onChange({ ...data, full_name: e.target.value })}
          required
        />
      </div>
      <div>
        <label className={labelCls}>גיל *</label>
        <input
          type="number"
          className={inputCls}
          placeholder="35"
          min={1}
          max={120}
          value={data.age}
          onChange={(e) => onChange({ ...data, age: e.target.value })}
          required
        />
      </div>
      <div>
        <label className={labelCls}>סיבת הפנייה / הבעיה העיקרית *</label>
        <textarea
          className={inputCls + ' resize-none'}
          rows={3}
          placeholder="לדוגמה: חרדה, קשיי שינה, משבר זוגי..."
          value={data.primary_concerns}
          onChange={(e) => onChange({ ...data, primary_concerns: e.target.value })}
          required
        />
      </div>
      <div>
        <label className={labelCls}>שיטת טיפול מועדפת</label>
        <select
          className={inputCls}
          value={data.therapy_approach}
          onChange={(e) => onChange({ ...data, therapy_approach: e.target.value })}
        >
          {THERAPY_APPROACHES.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}

// ── Main wizard ───────────────────────────────────────────────────────────────
export default function OnboardingWizard({ onComplete }: Props) {
  const [step, setStep] = useState(1)
  const [patient1, setPatient1] = useState<PatientForm>(emptyPatient())
  const [patient2, setPatient2] = useState<PatientForm>(emptyPatient())
  const [createdIds, setCreatedIds] = useState<{ id: number; name: string }[]>([])
  const [session, setSession] = useState<SessionForm>({
    patient_id: '',
    session_datetime: '',
    duration_minutes: '50',
    notes: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [prepBrief, setPrepBrief] = useState<PrepBrief | null>(null)
  const [aiLoading, setAiLoading] = useState(false)

  // On mount: if therapist already has patients, silently complete
  useEffect(() => {
    patientsAPI.list().then((patients: any[]) => {
      if (patients.length > 0) {
        therapistAPI.completeIntroWizard().catch(() => {})
        onComplete()
      }
    }).catch(() => {
      // If list fails, don't show wizard
      onComplete()
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const skip = async () => {
    try {
      await therapistAPI.completeIntroWizard()
    } catch {
      // best effort
    }
    onComplete()
  }

  const validatePatient = (p: PatientForm): string => {
    if (!p.full_name.trim()) return 'יש להזין שם מלא'
    if (!p.age || isNaN(Number(p.age)) || Number(p.age) < 1) return 'יש להזין גיל תקין'
    if (!p.primary_concerns.trim()) return 'יש להזין סיבת פנייה'
    return ''
  }

  const buildPrimaryConcerns = (p: PatientForm) =>
    `גיל: ${p.age}\n${p.primary_concerns}`

  // Step 1: create first patient → step 2
  const submitStep1 = async () => {
    const err = validatePatient(patient1)
    if (err) { setError(err); return }
    setError('')
    setLoading(true)
    try {
      const created = await patientsAPI.create({
        full_name: patient1.full_name,
        primary_concerns: buildPrimaryConcerns(patient1),
        diagnosis: patient1.therapy_approach !== 'other' ? `שיטת טיפול: ${patient1.therapy_approach}` : undefined,
      })
      setCreatedIds([{ id: created.id, name: created.full_name }])
      setSession((s) => ({ ...s, patient_id: String(created.id) }))
      setStep(2)
    } catch {
      setError('שגיאה בשמירת המטופל, נסה שוב')
    } finally {
      setLoading(false)
    }
  }

  // Step 2: create second patient → step 3
  const submitStep2 = async () => {
    const err = validatePatient(patient2)
    if (err) { setError(err); return }
    setError('')
    setLoading(true)
    try {
      const created = await patientsAPI.create({
        full_name: patient2.full_name,
        primary_concerns: buildPrimaryConcerns(patient2),
        diagnosis: patient2.therapy_approach !== 'other' ? `שיטת טיפול: ${patient2.therapy_approach}` : undefined,
      })
      setCreatedIds((prev) => [...prev, { id: created.id, name: created.full_name }])
      setStep(3)
    } catch {
      setError('שגיאה בשמירת המטופל, נסה שוב')
    } finally {
      setLoading(false)
    }
  }

  // Step 3: create session → AI prep (step 4)
  const submitStep3 = async () => {
    if (!session.patient_id) { setError('יש לבחור מטופל/ת'); return }
    if (!session.session_datetime) { setError('יש לבחור תאריך ושעה'); return }
    setError('')
    setLoading(true)
    try {
      const dt = new Date(session.session_datetime)
      const dateStr = dt.toISOString().split('T')[0]
      const created = await sessionsAPI.create({
        patient_id: Number(session.patient_id),
        session_date: dateStr,
        start_time: dt.toISOString(),
        duration_minutes: Number(session.duration_minutes),
      })

      // Trigger AI prep
      setStep(4)
      setLoading(false)
      setAiLoading(true)
      try {
        const brief = await sessionsAPI.getPrepBrief(created.id)
        setPrepBrief(brief)
      } catch {
        // If AI fails, show empty state gracefully
        setPrepBrief({ history_summary: [], last_session: [], tasks_to_check: [], focus_for_today: [], watch_out_for: [] })
      } finally {
        setAiLoading(false)
      }
    } catch {
      setError('שגיאה ביצירת הפגישה, נסה שוב')
      setLoading(false)
    }
  }

  const finishWizard = async () => {
    try {
      await therapistAPI.completeIntroWizard()
    } catch {
      // best effort
    }
    onComplete()
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
      dir="rtl"
    >
      <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-gray-800 flex-shrink-0">
          {step <= 3 && (
            <>
              <StepDots current={step} total={3} />
              <p className="text-center text-xs text-gray-500 mt-1">שלב {step} מתוך 3</p>
            </>
          )}
          {step === 4 && (
            <div className="text-center">
              <p className="text-lg font-bold text-white">✨ הכנה לפגישה שלך — נוצרה על ידי AI</p>
              <p className="text-xs text-gray-400 mt-1">כך מטפל אונליין מכין אותך לפני כל פגישה, אוטומטית.</p>
            </div>
          )}
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">

          {/* ── Step 1 ─────────────────────────────────────── */}
          {step === 1 && (
            <>
              <h2 className="text-lg font-bold text-white mb-1">בואו נתחיל — הוסיפו את המטופל הראשון שלכם</h2>
              <p className="text-sm text-gray-400 mb-5">המערכת עובדת הכי טוב עם מידע אמיתי.</p>
              <PatientFields data={patient1} onChange={setPatient1} />
            </>
          )}

          {/* ── Step 2 ─────────────────────────────────────── */}
          {step === 2 && (
            <>
              <h2 className="text-lg font-bold text-white mb-1">מצוין! עכשיו הוסיפו מטופל נוסף</h2>
              <p className="text-sm text-gray-400 mb-5">כשמוסיפים 2+ מטופלים המערכת מתחילה לעבוד בשבילך.</p>
              <PatientFields data={patient2} onChange={setPatient2} />
            </>
          )}

          {/* ── Step 3 ─────────────────────────────────────── */}
          {step === 3 && (
            <>
              <h2 className="text-lg font-bold text-white mb-1">קביעת פגישה ראשונה</h2>
              <p className="text-sm text-gray-400 mb-5">בחרו מטופל/ת וקבעו פגישה במערכת.</p>
              <div className="space-y-4">
                <div>
                  <label className={labelCls}>שם המטופל/ת *</label>
                  <select
                    className={inputCls}
                    value={session.patient_id}
                    onChange={(e) => setSession({ ...session, patient_id: e.target.value })}
                  >
                    <option value="">בחרו מטופל/ת...</option>
                    {createdIds.map((p) => (
                      <option key={p.id} value={String(p.id)}>{p.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className={labelCls}>תאריך ושעה *</label>
                  <input
                    type="datetime-local"
                    className={inputCls}
                    value={session.session_datetime}
                    onChange={(e) => setSession({ ...session, session_datetime: e.target.value })}
                  />
                </div>
                <div>
                  <label className={labelCls}>משך הפגישה</label>
                  <select
                    className={inputCls}
                    value={session.duration_minutes}
                    onChange={(e) => setSession({ ...session, duration_minutes: e.target.value })}
                  >
                    {DURATIONS.map((d) => (
                      <option key={d.value} value={d.value}>{d.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className={labelCls}>הערות לפגישה (אופציונלי)</label>
                  <textarea
                    className={inputCls + ' resize-none'}
                    rows={3}
                    placeholder="נושאים לדיון, רקע רלוונטי..."
                    value={session.notes}
                    onChange={(e) => setSession({ ...session, notes: e.target.value })}
                  />
                </div>
              </div>
            </>
          )}

          {/* ── Step 4: AI reveal ──────────────────────────── */}
          {step === 4 && (
            <>
              {aiLoading ? (
                <div className="flex flex-col items-center justify-center py-10 gap-4">
                  <div className="w-8 h-8 border-2 border-indigo-400/30 border-t-indigo-400 rounded-full animate-spin" />
                  <p className="text-sm text-gray-400">מכין את ההכנה שלך...</p>
                </div>
              ) : (
                <>
                  <PrepBriefDisplay brief={prepBrief} />

                  {/* Callout */}
                  <div className="mt-5 bg-indigo-950/60 border border-indigo-700/50 rounded-xl px-4 py-3.5 text-sm text-indigo-200 leading-relaxed">
                    <span className="font-semibold">💡 </span>
                    זו רק אחת מהיכולות של מטפל אונליין. לאחר כל פגישה, הקליטו או סכמו בקצרה, ואנו נדאג שתקבלו סיכום AI אוטומטי, תוכניות טיפול, תזכורות למטופלים ועוד.
                  </div>
                </>
              )}
            </>
          )}

          {/* Error banner */}
          {error && (
            <div className="mt-4 bg-red-950 border border-red-800 text-red-400 text-sm px-4 py-3 rounded-lg">
              {error}
            </div>
          )}
        </div>

        {/* Footer / actions */}
        <div className="px-6 pb-5 pt-3 border-t border-gray-800 flex-shrink-0">
          {step === 1 && (
            <div className="flex flex-col gap-2">
              <button
                onClick={submitStep1}
                disabled={loading}
                className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg transition-colors text-sm"
              >
                {loading ? <Spinner /> : 'הוספה והמשך'}
              </button>
              <div className="text-left">
                <button onClick={skip} className="text-xs text-gray-600 hover:text-gray-400 transition-colors">
                  דילוג על ההדרכה
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="flex flex-col gap-2">
              <button
                onClick={submitStep2}
                disabled={loading}
                className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg transition-colors text-sm"
              >
                {loading ? <Spinner /> : 'הוספה והמשך'}
              </button>
              <div className="flex justify-between items-center">
                <button
                  onClick={() => { setError(''); setStep(3) }}
                  className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                >
                  דילוג על שלב זה
                </button>
                <button onClick={skip} className="text-xs text-gray-600 hover:text-gray-400 transition-colors">
                  דילוג על ההדרכה
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="flex flex-col gap-2">
              <button
                onClick={submitStep3}
                disabled={loading}
                className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg transition-colors text-sm"
              >
                {loading ? <Spinner /> : 'סיימתי, פתח את המערכת'}
              </button>
              <div className="text-left">
                <button onClick={skip} className="text-xs text-gray-600 hover:text-gray-400 transition-colors">
                  דילוג על ההדרכה
                </button>
              </div>
            </div>
          )}

          {step === 4 && !aiLoading && (
            <button
              onClick={finishWizard}
              className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 rounded-xl transition-colors text-sm tracking-wide"
            >
              — ברוכים הבאים למטפל אונליין —
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Spinner helper ────────────────────────────────────────────────────────────
function Spinner() {
  return (
    <span className="flex items-center justify-center gap-2">
      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
      רגע...
    </span>
  )
}

// ── Prep brief display ────────────────────────────────────────────────────────
function PrepBriefDisplay({ brief }: { brief: PrepBrief | null }) {
  if (!brief) return null

  const sections: { key: keyof PrepBrief; label: string; color: string }[] = [
    { key: 'history_summary', label: 'רקע המטופל/ת', color: 'text-sky-400' },
    { key: 'focus_for_today', label: 'מיקוד לפגישה', color: 'text-indigo-400' },
    { key: 'tasks_to_check', label: 'בדקו בתחילת הפגישה', color: 'text-emerald-400' },
    { key: 'watch_out_for', label: 'שימו לב', color: 'text-amber-400' },
    { key: 'last_session', label: 'מהפגישה הקודמת', color: 'text-gray-400' },
  ]

  const hasContent = sections.some((s) => brief[s.key]?.length > 0)

  if (!hasContent) {
    return (
      <div className="bg-gray-800 rounded-xl p-4 text-sm text-gray-400 text-center">
        הפגישה נוצרה בהצלחה. ההכנה ה-AI תהיה זמינה לאחר הוספת סיכום פגישה ראשונה.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {sections
        .filter((s) => brief[s.key]?.length > 0)
        .map((s) => (
          <div key={s.key} className="bg-gray-800 rounded-xl px-4 py-3">
            <p className={`text-xs font-semibold uppercase tracking-wide mb-2 ${s.color}`}>{s.label}</p>
            <ul className="space-y-1">
              {brief[s.key].map((item, i) => (
                <li key={i} className="text-sm text-gray-300 flex gap-2">
                  <span className="text-gray-600 mt-0.5 flex-shrink-0">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
    </div>
  )
}
