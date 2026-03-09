/**
 * First-time data onboarding wizard.
 * Shown once to new therapists after completing the AI style onboarding.
 *
 * Steps:
 *  0 — Welcome screen (not counted in progress dots)
 *  1 — Add first patient
 *  2 — Add second patient (skippable)
 *  3 — Schedule a session
 *  4 — Static platform capabilities preview
 */

import { useState, useEffect } from 'react'
import DatePicker from 'react-datepicker'
import 'react-datepicker/dist/react-datepicker.css'
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
  session_date: Date | null
  session_time: string   // "HH:MM"
  duration_minutes: string
  notes: string
}

const emptyPatient = (): PatientForm => ({
  full_name: '',
  age: '',
  primary_concerns: '',
  therapy_approach: '',
})

const DURATIONS = [
  { value: '45', label: '45 דקות' },
  { value: '50', label: '50 דקות' },
  { value: '60', label: '60 דקות' },
  { value: '90', label: '90 דקות' },
]

// 15-minute time slots 07:00 → 22:00
const TIME_SLOTS: string[] = []
for (let h = 7; h <= 22; h++) {
  for (let m = 0; m < 60; m += 15) {
    if (h === 22 && m > 0) break
    TIME_SLOTS.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`)
  }
}

// Label map for therapy approach values
const APPROACH_LABELS: Record<string, string> = {
  CBT: 'CBT — קוגניטיבי התנהגותי',
  DBT: 'DBT — דיאלקטי התנהגותי',
  ACT: 'ACT — קבלה ומחויבות',
  psychodynamic: 'פסיכודינמי',
  humanistic: 'הומניסטי',
  integrative: 'אינטגרטיבי',
  other: 'כללי / אחר',
}

// ── Shared styles ─────────────────────────────────────────────────────────────
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
  therapistMethods,
}: {
  data: PatientForm
  onChange: (f: PatientForm) => void
  therapistMethods: string[]
}) {
  const singleMethod = therapistMethods.length === 1 ? therapistMethods[0] : null

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
        />
      </div>
      <div>
        <label className={labelCls}>
          גיל <span className="text-gray-500 font-normal">(אופציונלי)</span>
        </label>
        <input
          type="number"
          className={inputCls}
          placeholder="35"
          min={1}
          max={120}
          value={data.age}
          onChange={(e) => onChange({ ...data, age: e.target.value })}
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
        />
      </div>
      <div>
        <label className={labelCls}>שיטת טיפול מועדפת</label>
        {singleMethod ? (
          <>
            <div className={inputCls + ' cursor-default text-gray-300'}>
              {APPROACH_LABELS[singleMethod] ?? singleMethod}
            </div>
            <p className="text-xs text-gray-600 mt-1">ניתן לשינוי בתוך המערכת בהגדרות</p>
          </>
        ) : (
          <select
            className={inputCls}
            value={data.therapy_approach}
            onChange={(e) => onChange({ ...data, therapy_approach: e.target.value })}
          >
            <option value="">בחרו שיטה...</option>
            {therapistMethods.map((m) => (
              <option key={m} value={m}>
                {APPROACH_LABELS[m] ?? m}
              </option>
            ))}
          </select>
        )}
      </div>
    </div>
  )
}

// ── Static platform preview (step 4) ─────────────────────────────────────────
const PREVIEW_CARDS = [
  {
    icon: '📋',
    title: 'רקע המטופל',
    text: 'סיכום מצטבר של כל הפגישות הקודמות, כתוב בצורה ברורה ומובנית, כדי שתיכנסו לכל פגישה עם תמונה מלאה על מצב המטופל.',
  },
  {
    icon: '🎯',
    title: 'מיקוד לפגישה הקרובה',
    text: 'נושאים מרכזיים לדיון על בסיס מה שעלה בפגישות קודמות, משימות פתוחות ודברים כלליים שביקשתם לבדוק, הכל מוכן ומסוכם מראש.',
  },
  {
    icon: '✅',
    title: 'תזכורות ומשימות פתוחות',
    text: 'רשימת משימות שהוגדרו בפגישות קודמות, כדי שלא תפספסו דבר ותוכלו להמשיך בדיוק מהנקודה שעצרתם.',
  },
  {
    icon: '📝',
    title: 'סיכום פגישה בלחיצה אחת',
    text: 'בסיום כל פגישה, המערכת תייצר עבורכם סיכום מפורט שתוכלו לערוך ולאשר, חוסך זמן יקר של אדמיניסטרציה ותיעוד.',
  },
]

function PlatformPreview() {
  return (
    <div className="space-y-3">
      {PREVIEW_CARDS.map((card) => (
        <div key={card.title} className="bg-gray-800 rounded-xl px-4 py-3.5 flex gap-3">
          <span className="text-xl flex-shrink-0 mt-0.5">{card.icon}</span>
          <div>
            <p className="text-sm font-semibold text-white mb-1">{card.title}</p>
            <p className="text-xs text-gray-400 leading-relaxed">{card.text}</p>
          </div>
        </div>
      ))}
      <div className="bg-indigo-950/60 border border-indigo-700/50 rounded-xl px-4 py-3.5 text-sm text-indigo-200 leading-relaxed">
        <span className="font-semibold">💡 </span>
        ככל שתשתמשו במערכת יותר, כך הסיכומים והתכניות יהיו מדויקים ומותאמים יותר עבורך לטובת המטופל והעבודה השוטפת.
      </div>
    </div>
  )
}

// ── Main wizard ───────────────────────────────────────────────────────────────
export default function OnboardingWizard({ onComplete }: Props) {
  const [step, setStep] = useState(0)
  const [patient1, setPatient1] = useState<PatientForm>(emptyPatient())
  const [patient2, setPatient2] = useState<PatientForm>(emptyPatient())
  const [createdIds, setCreatedIds] = useState<{ id: number; name: string }[]>([])
  const [session, setSession] = useState<SessionForm>({
    patient_id: '',
    session_date: null,
    session_time: '10:00',
    duration_minutes: '50',
    notes: '',
  })
  const [therapistMethods, setTherapistMethods] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // On mount: check for existing patients + load therapist's therapy methods
  useEffect(() => {
    patientsAPI.list().then((patients: any[]) => {
      console.log('[OnboardingWizard] patient count on mount:', patients.length)
      if (patients.length > 0) {
        // Therapist already has patients — silently complete the wizard
        console.log('[OnboardingWizard] existing patients found — auto-completing wizard')
        therapistAPI.completeIntroWizard().catch(() => {})
        onComplete()
      } else {
        console.log('[OnboardingWizard] no patients — showing wizard')
      }
    }).catch((err: any) => {
      // List failed — do NOT complete the wizard; just show it
      console.log('[OnboardingWizard] patient list failed (will show wizard):', err?.message ?? err)
    })

    therapistAPI.getProfile().then((profile: any) => {
      const modes: string[] = profile.primary_therapy_modes ?? []
      if (modes.length > 0) {
        setTherapistMethods(modes)
        if (modes.length === 1) {
          setPatient1((p) => ({ ...p, therapy_approach: modes[0] }))
          setPatient2((p) => ({ ...p, therapy_approach: modes[0] }))
        }
      } else if (profile.therapeutic_approach) {
        const m = profile.therapeutic_approach
        setTherapistMethods([m])
        setPatient1((p) => ({ ...p, therapy_approach: m }))
        setPatient2((p) => ({ ...p, therapy_approach: m }))
      } else {
        setTherapistMethods(Object.keys(APPROACH_LABELS))
      }
    }).catch(() => {
      setTherapistMethods(Object.keys(APPROACH_LABELS))
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const skip = async () => {
    try { await therapistAPI.completeIntroWizard() } catch { /* best effort */ }
    onComplete()
  }

  const validatePatient = (p: PatientForm): string => {
    if (!p.full_name.trim()) return 'יש להזין שם מלא'
    // Age is optional — skip age validation
    if (!p.primary_concerns.trim()) return 'יש להזין סיבת פנייה'
    return ''
  }

  const buildPrimaryConcerns = (p: PatientForm) =>
    p.age ? `גיל: ${p.age}\n${p.primary_concerns}` : p.primary_concerns

  const createPatient = async (p: PatientForm) =>
    patientsAPI.create({
      full_name: p.full_name,
      primary_concerns: buildPrimaryConcerns(p),
      diagnosis: p.therapy_approach && p.therapy_approach !== 'other'
        ? `שיטת טיפול: ${p.therapy_approach}`
        : undefined,
    })

  const submitStep1 = async () => {
    const err = validatePatient(patient1)
    if (err) { setError(err); return }
    setError('')
    setLoading(true)
    try {
      const created = await createPatient(patient1)
      setCreatedIds([{ id: created.id, name: created.full_name }])
      setSession((s) => ({ ...s, patient_id: String(created.id) }))
      setStep(2)
    } catch {
      setError('שגיאה בשמירת המטופל, נסה שוב')
    } finally {
      setLoading(false)
    }
  }

  const submitStep2 = async () => {
    const err = validatePatient(patient2)
    if (err) { setError(err); return }
    setError('')
    setLoading(true)
    try {
      const created = await createPatient(patient2)
      setCreatedIds((prev) => [...prev, { id: created.id, name: created.full_name }])
      setStep(3)
    } catch {
      setError('שגיאה בשמירת המטופל, נסה שוב')
    } finally {
      setLoading(false)
    }
  }

  const submitStep3 = async () => {
    if (!session.patient_id) { setError('יש לבחור מטופל/ת'); return }
    if (!session.session_date) { setError('יש לבחור תאריך'); return }
    setError('')
    setLoading(true)
    try {
      // Combine selected date + time into ISO datetime
      const [hh, mm] = session.session_time.split(':').map(Number)
      const dt = new Date(session.session_date)
      dt.setHours(hh, mm, 0, 0)
      const sessionDateStr = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`
      await sessionsAPI.create({
        patient_id: Number(session.patient_id),
        session_date: sessionDateStr,
        start_time: dt.toISOString(),
        duration_minutes: Number(session.duration_minutes),
      })
      setStep(4)
    } catch {
      setError('שגיאה ביצירת הפגישה, נסה שוב')
    } finally {
      setLoading(false)
    }
  }

  const finishWizard = async () => {
    try { await therapistAPI.completeIntroWizard() } catch { /* best effort */ }
    onComplete()
  }

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
      dir="rtl"
    >
      <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-gray-800 flex-shrink-0">
          {step >= 1 && step <= 3 && (
            <>
              <StepDots current={step} total={3} />
              <p className="text-center text-xs text-gray-500 mt-1">שלב {step} מתוך 3</p>
            </>
          )}
          {step === 4 && (
            <div className="text-center">
              <p className="text-lg font-bold text-white">✨ זה מה שמטפל אונליין יכין לך לפני כל פגישה</p>
              <p className="text-xs text-gray-400 mt-1">לאחר כמה פגישות, המערכת תייצר את כל זה אוטומטית עבורך</p>
            </div>
          )}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">

          {/* Step 0 — Welcome */}
          {step === 0 && (
            <div className="space-y-5 py-2">
              <p className="text-2xl font-bold text-white leading-snug text-center">
                ברוכים הבאים למטפל אונליין 👋
              </p>
              <p className="text-sm text-gray-300 leading-relaxed">
                כדי שהמערכת תוכל לעבוד עבורכם מהיום הראשון, נבקש מכם להכניס פרטים של מטופל אחד-שניים ופגישה קרובה איתם.
                <br /><br />
                זה לוקח כ-2 דקות, ובסיומם תראו בדיוק איך המערכת עוזרת לכם להתכונן לכל פגישה.
              </p>
            </div>
          )}

          {step === 1 && (
            <>
              <h2 className="text-lg font-bold text-white mb-1">בואו נתחיל — הוסיפו את המטופל הראשון שלכם</h2>
              <p className="text-sm text-gray-400 mb-5">המערכת עובדת הכי טוב עם מידע אמיתי.</p>
              <PatientFields data={patient1} onChange={setPatient1} therapistMethods={therapistMethods} />
            </>
          )}

          {step === 2 && (
            <>
              <h2 className="text-lg font-bold text-white mb-1">הוסיפו בבקשה פרטי מטופל שני</h2>
              <p className="text-sm text-gray-400 mb-5">כשמוסיפים 2+ מטופלים המערכת מתחילה לעבוד בשבילך.</p>
              <PatientFields data={patient2} onChange={setPatient2} therapistMethods={therapistMethods} />
            </>
          )}

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

                {/* Date + time — two separate fields */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={labelCls}>תאריך *</label>
                    <DatePicker
                      selected={session.session_date}
                      onChange={(date: Date | null) => setSession({ ...session, session_date: date })}
                      dateFormat="dd/MM/yyyy"
                      minDate={new Date()}
                      placeholderText="DD/MM/YYYY"
                      className={inputCls + ' cursor-pointer'}
                      wrapperClassName="w-full"
                      popperPlacement="bottom-start"
                    />
                  </div>
                  <div>
                    <label className={labelCls}>שעה *</label>
                    <select
                      className={inputCls}
                      value={session.session_time}
                      onChange={(e) => setSession({ ...session, session_time: e.target.value })}
                    >
                      {TIME_SLOTS.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </div>
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

          {step === 4 && <PlatformPreview />}

          {error && (
            <div className="mt-4 bg-red-950 border border-red-800 text-red-400 text-sm px-4 py-3 rounded-lg">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 pb-5 pt-3 border-t border-gray-800 flex-shrink-0">
          {step === 0 && (
            <div className="flex flex-col gap-3">
              <button
                onClick={() => setStep(1)}
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2.5 rounded-lg transition-colors text-sm"
              >
                בואו נתחיל ←
              </button>
              <div className="text-center">
                <button onClick={skip} className="text-xs text-gray-600 hover:text-gray-400 transition-colors">
                  אין צורך, אכניס בעצמי בתוך המערכת
                </button>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="flex flex-col gap-2">
              <button
                onClick={submitStep1}
                disabled={loading}
                className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg transition-colors text-sm"
              >
                {loading ? <Spinner /> : 'המשך'}
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
                {loading ? <Spinner /> : 'מסך אחרון ודי..'}
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
                {loading ? <Spinner /> : 'כניסה למערכת'}
              </button>
              <div className="text-left">
                <button onClick={skip} className="text-xs text-gray-600 hover:text-gray-400 transition-colors">
                  דילוג על ההדרכה
                </button>
              </div>
            </div>
          )}

          {step === 4 && (
            <button
              onClick={finishWizard}
              className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 rounded-xl transition-colors text-sm"
            >
              כניסה למערכת
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function Spinner() {
  return (
    <span className="flex items-center justify-center gap-2">
      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
      רגע...
    </span>
  )
}
