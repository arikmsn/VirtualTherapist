import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { agentAPI, therapistAPI } from '@/lib/api'
import { useAuth } from '@/auth/useAuth'
import { CheckIcon } from '@heroicons/react/24/solid'
import AppLogo from '@/components/common/AppLogo'

const STEPS = [
  { title: 'גישה טיפולית', description: 'מהי הגישה הטיפולית שלך' },
  { title: 'סגנון כתיבה', description: 'תיאור של הסיכומים הקיימים שלך' },
  { title: 'רקע מקצועי', description: 'פרטים שיעזרו לבינה המלאכותית להבין את הרקע שלך' },
  { title: 'דוגמאות ללמידה', description: 'דוגמאות כדי שהמערכת תלמד את הסגנון האישי שלך (לא חובה)' },
]

const THERAPEUTIC_APPROACHES = [
  { value: 'CBT', label: 'CBT — טיפול קוגניטיבי-התנהגותי' },
  { value: 'psychodynamic', label: 'פסיכודינמית' },
  { value: 'humanistic', label: 'הומניסטית' },
  { value: 'DBT', label: 'DBT — טיפול דיאלקטי-התנהגותי' },
  { value: 'ACT', label: 'ACT — קבלה ומחויבות' },
  { value: 'EMDR', label: 'EMDR' },
  { value: 'gestalt', label: 'גשטלט' },
  { value: 'integrative', label: 'אינטגרטיבית' },
  { value: 'psychodrama', label: 'פסיכודרמה' },
  { value: 'other', label: 'אחר' },
]

const APPROACH_EXAMPLES: Record<string, string> = {
  CBT: 'לדוגמה: אני עובד בדרך כלל עם CBT ממוקד מטרה, כולל שיעורי בית ותרגול בין מפגשים.',
  psychodynamic: 'לדוגמה: אני עובד בגישה דינמית, עם דגש על יחסים, דפוסים חוזרים ועולם פנימי.',
  humanistic: 'לדוגמה: אני מלווה את המטופל בתהליך של גדילה אישית, תוך דגש על הפוטנציאל הקיים.',
  DBT: 'לדוגמה: אני משלב רגולציה רגשית, מיינדפולנס וכישורי סבילות למצוקה.',
  ACT: 'לדוגמה: אני עובד על קבלת מחשבות ורגשות תוך מחויבות לפעולה בהתאם לערכים האישיים.',
  EMDR: 'לדוגמה: אני משתמש ב-EMDR לעיבוד זיכרונות טראומטיים ולהפחתת תגובות פוסט-טראומטיות.',
  gestalt: 'לדוגמה: אני עובד בגישת גשטלט, עם דגש על מודעות לרגע הנוכחי וניסוי ישיר.',
  integrative: 'לדוגמה: אני משלב גישות שונות — CBT, פסיכודינמיקה ועבודה גופנית — לפי צרכי המטופל.',
  psychodrama: 'לדוגמה: אני משתמש בטכניקות פסיכודרמה כדי לחקור ולשנות דפוסים רגשיים.',
  other: 'תאר בקצרה את הגישה הטיפולית שלך, הטכניקות העיקריות ואופן העבודה שלך...',
}

const TONE_OPTIONS = [
  'פורמלי',
  'מקצועי אך נגיש',
  'חברי',
  'ישיר ותכליתי',
  'אמפתי ורך',
]

export default function OnboardingPage() {
  const navigate = useNavigate()
  const { markOnboardingComplete, logout } = useAuth()
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const [form, setForm] = useState({
    approach: '',
    approachDescription: '',
    toneExtra: '',
    messageLength: 'medium',
    terminology: '',
    education: '',
    certifications: '',
    yearsOfExperience: '',
    areasOfExpertise: '',
    exampleSummary: '',
    exampleMessage: '',
  })
  const [selectedTones, setSelectedTones] = useState<string[]>([])

  const set = (field: keyof typeof form, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }))

  const toggleTone = (tone: string) =>
    setSelectedTones((prev) =>
      prev.includes(tone) ? prev.filter((t) => t !== tone) : [...prev, tone]
    )

  // Combines chip selections + free-text extra into a single tone string for the backend
  const buildToneString = () =>
    [...selectedTones, form.toneExtra].filter(Boolean).join(', ')

  const canAdvance = (): boolean => {
    if (step === 0) return form.approach !== ''
    if (step === 1) return selectedTones.length > 0 || form.toneExtra.trim() !== ''
    return true
  }

  const handleNext = async () => {
    if (!canAdvance()) return
    setSaving(true)
    setError('')
    try {
      // Save current step data to backend
      if (step === 0) {
        await agentAPI.completeOnboardingStep(1, {
          approach: form.approach,
          approachDescription: form.approachDescription,
        })
      } else if (step === 1) {
        await agentAPI.completeOnboardingStep(2, {
          tone: buildToneString(),
          messageLength: form.messageLength,
          terminology: form.terminology,
        })
      } else if (step === 2) {
        await therapistAPI.updateTwinControls({
          education: form.education || null,
          certifications: form.certifications || null,
          years_of_experience: form.yearsOfExperience || null,
          areas_of_expertise: form.areasOfExpertise || null,
        })
      } else if (step === 3) {
        // Optional examples step — only save if provided
        if (form.exampleSummary || form.exampleMessage) {
          await agentAPI.completeOnboardingStep(5, {
            exampleSummary: form.exampleSummary,
            exampleMessage: form.exampleMessage,
          })
        }
        // Mark onboarding complete on the backend
        await therapistAPI.completeOnboarding()
        markOnboardingComplete()
        navigate('/dashboard', { replace: true })
        return
      }
      setStep((s) => s + 1)
    } catch {
      setError('אירעה שגיאה בשמירה. אנא נסה שוב.')
    } finally {
      setSaving(false)
    }
  }


  const handleExit = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50 flex flex-col" dir="rtl">
      {/* Header bar */}
      <header className="bg-white border-b border-gray-100 px-6 py-3.5 flex items-center justify-between">
        <AppLogo variant="full" size="md" />
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-400">הגדרות ראשוניות — שלב {step + 1} מתוך {STEPS.length}</span>
          <button
            type="button"
            onClick={handleExit}
            className="text-sm text-gray-400 hover:text-gray-700 border border-gray-200 rounded-lg px-3 py-1.5 transition-colors"
          >
            יציאה
          </button>
        </div>
      </header>

      {/* Progress */}
      <div className="h-1 bg-gray-100">
        <div
          className="h-1 bg-indigo-500 transition-all duration-500"
          style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 flex items-start justify-center py-12 px-4">
        <div className="w-full max-w-xl">
          {/* Step indicators — centered across the full card width */}
          <div className="flex items-center justify-center gap-2 mb-8">
            {STEPS.map((_, i) => (
              <div key={i} className="flex items-center gap-2">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-colors ${
                    i < step
                      ? 'bg-indigo-600 text-white'
                      : i === step
                      ? 'bg-indigo-100 text-indigo-700 ring-2 ring-indigo-400'
                      : 'bg-gray-100 text-gray-400'
                  }`}
                >
                  {i < step ? <CheckIcon className="h-4 w-4" /> : i + 1}
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`h-px w-8 ${i < step ? 'bg-indigo-400' : 'bg-gray-200'}`} />
                )}
              </div>
            ))}
          </div>

          {/* Card */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
            <h2 className="text-xl font-bold text-gray-900 mb-1">{STEPS[step].title}</h2>
            <p className="text-sm text-gray-500 mb-6">{STEPS[step].description}</p>

            {/* Step 1 — Therapeutic Approach */}
            {step === 0 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    גישה טיפולית <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={form.approach}
                    onChange={(e) => set('approach', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white"
                  >
                    <option value="">בחר גישה...</option>
                    {THERAPEUTIC_APPROACHES.map((a) => (
                      <option key={a.value} value={a.value}>{a.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    תיאור הגישה שלך (לא חובה)
                  </label>
                  <textarea
                    value={form.approachDescription}
                    onChange={(e) => set('approachDescription', e.target.value)}
                    rows={4}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
                    placeholder="תאר בקצרה את אופן העבודה שלך, הטכניקות העיקריות ומה מייחד את הגישה שלך..."
                  />
                  {form.approach && APPROACH_EXAMPLES[form.approach] && (
                    <p className="mt-1.5 text-xs text-gray-400 leading-relaxed">
                      {APPROACH_EXAMPLES[form.approach]}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Step 2 — Writing Style */}
            {step === 1 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    טון כתיבה <span className="text-red-500">*</span>
                  </label>
                  {/* Tone chips */}
                  <div className="flex flex-wrap gap-2 mb-2">
                    {TONE_OPTIONS.map((tone) => (
                      <button
                        key={tone}
                        type="button"
                        onClick={() => toggleTone(tone)}
                        className={`px-3.5 py-1.5 rounded-full text-sm border transition-colors ${
                          selectedTones.includes(tone)
                            ? 'bg-indigo-600 text-white border-indigo-600'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-indigo-300'
                        }`}
                      >
                        {tone}
                      </button>
                    ))}
                  </div>
                  {/* Free-text extra */}
                  <input
                    type="text"
                    value={form.toneExtra}
                    onChange={(e) => set('toneExtra', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                    placeholder="הוספות חופשיות, למשל: חם אך גבולות ברורים..."
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    אורך סיכום מועדף
                  </label>
                  <div className="flex gap-3">
                    {[
                      { value: 'short', label: 'קצר' },
                      { value: 'medium', label: 'בינוני' },
                      { value: 'detailed', label: 'מפורט' },
                    ].map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => set('messageLength', opt.value)}
                        className={`flex-1 py-2.5 rounded-lg text-sm font-medium border transition-colors ${
                          form.messageLength === opt.value
                            ? 'bg-indigo-600 text-white border-indigo-600'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-indigo-300'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    האם יש מינוחים מועדפים להשתמש בהם (לא חובה)
                  </label>
                  <input
                    type="text"
                    value={form.terminology}
                    onChange={(e) => set('terminology', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                    placeholder="מילות מפתח שאתה משתמש בהן בסיכומים, הפרד בפסיקים..."
                  />
                </div>
              </div>
            )}

            {/* Step 3 — Professional Background */}
            {step === 2 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    השכלה אקדמית
                  </label>
                  <input
                    type="text"
                    value={form.education}
                    onChange={(e) => set('education', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                    placeholder="למשל: M.A. פסיכולוגיה קלינית, אוניברסיטת ת״א"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    תארים ורישיונות מקצועיים
                  </label>
                  <input
                    type="text"
                    value={form.certifications}
                    onChange={(e) => set('certifications', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                    placeholder="למשל: פסיכולוג קליני מורשה, מטפל EMDR מוסמך"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      שנות ניסיון
                    </label>
                    <input
                      type="text"
                      value={form.yearsOfExperience}
                      onChange={(e) => set('yearsOfExperience', e.target.value)}
                      className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                      placeholder="למשל: 8"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      תחומי התמחות
                    </label>
                    <input
                      type="text"
                      value={form.areasOfExpertise}
                      onChange={(e) => set('areasOfExpertise', e.target.value)}
                      className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                      placeholder="חרדה, טראומה, זוגיות..."
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Step 4 — Learning Examples (optional) */}
            {step === 3 && (
              <div className="space-y-4">
                <p className="text-xs text-gray-400 bg-gray-50 rounded-lg p-3">
                  דוגמאות עוזרות לבינה המלאכותית ללמוד את הסגנון הייחודי שלך. ניתן לדלג על שלב זה ולהוסיף מאוחר יותר.
                </p>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    דוגמא לסיכום פגישה שכתבת
                  </label>
                  <textarea
                    value={form.exampleSummary}
                    onChange={(e) => set('exampleSummary', e.target.value)}
                    rows={5}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
                    placeholder="הכנס כאן סיכום פגישה לדוגמא — ניתן למחוק פרטים מזהים..."
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    דוגמא להודעה ששלחת למטופל
                  </label>
                  <textarea
                    value={form.exampleMessage}
                    onChange={(e) => set('exampleMessage', e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
                    placeholder="הכנס כאן הודעה לדוגמא..."
                  />
                  <p className="mt-1.5 text-xs text-gray-400 leading-relaxed">
                    אפשר להדביק כאן הודעה טיפוסית ששלחת למטופל — למשל תזכורת לפגישה, משימה בין מפגשים, הודעת תמיכה קצרה או עדכון חשוב. השדה אופציונלי ומסייע למערכת ללמוד את סגנון התקשורת שלך עם מטופלים.
                  </p>
                </div>
              </div>
            )}

            {error && (
              <p className="text-red-600 text-sm mt-4">{error}</p>
            )}
          </div>

          {/* Navigation */}
          <div className="flex items-center justify-between mt-6">
            <button
              type="button"
              onClick={() => setStep((s) => Math.max(0, s - 1))}
              disabled={step === 0 || saving}
              className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              חזרה
            </button>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleNext}
                disabled={saving || !canAdvance()}
                className="px-6 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {saving ? 'שומר...' : step === STEPS.length - 1 ? 'סיום' : 'המשך'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
