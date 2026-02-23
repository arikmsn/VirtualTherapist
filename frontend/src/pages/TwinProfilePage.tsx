/**
 * TwinProfilePage — Living Therapist Twin v0.1 profile.
 *
 * Shows the therapist's AI style profile as an editable, living representation.
 * Onboarding-collected data is displayed read-only.
 * Twin controls (tone warmth, directiveness, prohibitions, custom rules) are editable.
 * Changes take effect immediately on all subsequent AI calls.
 *
 * PRD reference: Feature 5 — Therapist Profile (Twin v0.1)
 */

import { useState, useEffect } from 'react'
import {
  SparklesIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  PlusIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { therapistAPI } from '@/lib/api'

interface TherapistProfile {
  id: number
  therapist_id: number
  therapeutic_approach: string
  approach_description: string | null
  tone: string | null
  message_length_preference: string | null
  common_terminology: string[] | null
  follow_up_frequency: string | null
  preferred_exercises: string[] | null
  onboarding_completed: boolean
  onboarding_step: number
  // Twin controls
  tone_warmth: number
  directiveness: number
  prohibitions: string[]
  custom_rules: string | null
  style_version: number
  // Professional credentials
  education: string | null
  certifications: string | null
  years_of_experience: string | null
  areas_of_expertise: string | null
}

const MODALITIES = [
  { value: 'CBT', label: 'CBT — קוגניטיבי-התנהגותי' },
  { value: 'DBT', label: 'DBT — דיאלקטי-התנהגותי' },
  { value: 'ACT', label: 'ACT — קבלה ומחויבות' },
  { value: 'EMDR', label: 'EMDR' },
  { value: 'psychodynamic', label: 'פסיכודינמי' },
  { value: 'humanistic', label: 'הומניסטי' },
  { value: 'gestalt', label: 'גשטלט' },
  { value: 'integrative', label: 'אינטגרטיבי' },
  { value: 'psychodrama', label: 'פסיכודרמה' },
  { value: 'other', label: 'אחר' },
]

const MODALITY_VALUES = MODALITIES.map((m) => m.value)

function parseModalities(profile: TherapistProfile): string[] {
  const result = new Set<string>()
  if (profile.therapeutic_approach) result.add(profile.therapeutic_approach)
  if (profile.approach_description) {
    profile.approach_description.split(',').map((s) => s.trim()).forEach((v) => {
      if (MODALITY_VALUES.includes(v)) result.add(v)
    })
  }
  return [...result]
}

const WARMTH_LABELS: Record<number, string> = {
  1: 'פורמלי מאוד',
  2: 'פורמלי',
  3: 'מאוזן',
  4: 'חמים',
  5: 'חמים מאוד',
}

const DIRECTIVE_LABELS: Record<number, string> = {
  1: 'חקרני מאוד',
  2: 'חקרני',
  3: 'מאוזן',
  4: 'מכוון',
  5: 'מכוון מאוד',
}

function SliderControl({
  label,
  leftLabel,
  rightLabel,
  value,
  onChange,
  valueLabels,
}: {
  label: string
  leftLabel: string
  rightLabel: string
  value: number
  onChange: (v: number) => void
  valueLabels: Record<number, string>
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-gray-700">{label}</label>
        <span className="text-sm font-semibold text-therapy-calm px-3 py-0.5 bg-blue-50 rounded-full">
          {valueLabels[value]}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-gray-400 w-16 text-left">{leftLabel}</span>
        <input
          type="range"
          min={1}
          max={5}
          step={1}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-therapy-calm"
        />
        <span className="text-xs text-gray-400 w-16 text-right">{rightLabel}</span>
      </div>
      {/* Tick marks */}
      <div className="flex justify-between px-[72px]">
        {[1, 2, 3, 4, 5].map((v) => (
          <div
            key={v}
            className={`text-xs text-center w-5 ${value === v ? 'text-therapy-calm font-bold' : 'text-gray-300'}`}
          >
            {v}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function TwinProfilePage() {
  const [profile, setProfile] = useState<TherapistProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Editable Twin control state
  const [toneWarmth, setToneWarmth] = useState(3)
  const [directiveness, setDirectiveness] = useState(3)
  const [prohibitions, setProhibitions] = useState<string[]>([])
  const [customRules, setCustomRules] = useState('')
  const [newProhibition, setNewProhibition] = useState('')

  // Therapeutic modalities (multi-select for approach_description)
  const [selectedModalities, setSelectedModalities] = useState<string[]>([])
  const [initModalities, setInitModalities] = useState<string[]>([])

  // Professional credentials
  const [education, setEducation] = useState('')
  const [certifications, setCertifications] = useState('')
  const [yearsOfExperience, setYearsOfExperience] = useState('')
  const [areasOfExpertise, setAreasOfExpertise] = useState('')

  // Save state
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState('')

  const isDirty =
    profile !== null && (
      toneWarmth !== profile.tone_warmth ||
      directiveness !== profile.directiveness ||
      customRules !== (profile.custom_rules || '') ||
      JSON.stringify(prohibitions) !== JSON.stringify(profile.prohibitions || []) ||
      JSON.stringify([...selectedModalities].sort()) !== JSON.stringify([...initModalities].sort()) ||
      education !== (profile.education || '') ||
      certifications !== (profile.certifications || '') ||
      yearsOfExperience !== (profile.years_of_experience || '') ||
      areasOfExpertise !== (profile.areas_of_expertise || '')
    )

  useEffect(() => {
    const load = async () => {
      try {
        const data: TherapistProfile = await therapistAPI.getProfile()
        setProfile(data)
        setToneWarmth(data.tone_warmth)
        setDirectiveness(data.directiveness)
        setProhibitions(data.prohibitions || [])
        setCustomRules(data.custom_rules || '')
        const mods = parseModalities(data)
        setSelectedModalities(mods)
        setInitModalities(mods)
        setEducation(data.education || '')
        setCertifications(data.certifications || '')
        setYearsOfExperience(data.years_of_experience || '')
        setAreasOfExpertise(data.areas_of_expertise || '')
      } catch (err: any) {
        setError(err.response?.data?.detail || 'שגיאה בטעינת הפרופיל')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setSaveError('')
    setSaveSuccess(false)
    try {
      const updated = await therapistAPI.updateTwinControls({
        tone_warmth: toneWarmth,
        directiveness,
        prohibitions,
        custom_rules: customRules || null,
        approach_description: selectedModalities.length > 0 ? selectedModalities.join(', ') : null,
        education: education || null,
        certifications: certifications || null,
        years_of_experience: yearsOfExperience || null,
        areas_of_expertise: areasOfExpertise || null,
      })
      setProfile(updated)
      const mods = parseModalities(updated)
      setInitModalities(mods)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err: any) {
      setSaveError(err.response?.data?.detail || 'שגיאה בשמירה')
    } finally {
      setSaving(false)
    }
  }

  const addProhibition = () => {
    const trimmed = newProhibition.trim()
    if (!trimmed || prohibitions.includes(trimmed)) return
    setProhibitions([...prohibitions, trimmed])
    setNewProhibition('')
  }

  const removeProhibition = (idx: number) => {
    setProhibitions(prohibitions.filter((_, i) => i !== idx))
  }

  // --- Loading / Error ---

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" dir="rtl">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-therapy-calm mx-auto mb-4"></div>
          <p className="text-gray-600">טוען פרופיל...</p>
        </div>
      </div>
    )
  }

  if (error || !profile) {
    return (
      <div className="max-w-3xl mx-auto py-8" dir="rtl">
        <div className="card text-center py-12">
          <ExclamationTriangleIcon className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-700">{error || 'פרופיל לא נמצא'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in" dir="rtl">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <SparklesIcon className="h-6 w-6 text-therapy-calm" />
            <h1 className="text-2xl font-bold text-gray-900">פרופיל ה-Twin שלי</h1>
          </div>
          <p className="text-gray-600 mt-1 text-sm">
            כך ה-AI מדמה את הסגנון הטיפולי שלך — ערוך וכוון לפי הצורך
          </p>
        </div>
        <div className="text-xs text-gray-400 text-left">
          <div className="font-medium text-gray-500">גרסת סגנון</div>
          <div className="text-lg font-bold text-therapy-calm">v{profile.style_version}</div>
        </div>
      </div>

      {/* ── Section 1: Therapeutic modalities (editable multi-select) ── */}
      <div className="card">
        <h2 className="text-lg font-bold text-gray-800 mb-1">גישות טיפוליות</h2>
        <p className="text-sm text-gray-500 mb-4">בחר את כל השיטות הטיפוליות בהן אתה עובד</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {MODALITIES.map((m) => {
            const checked = selectedModalities.includes(m.value)
            return (
              <label
                key={m.value}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors text-sm ${
                  checked
                    ? 'border-therapy-calm bg-blue-50 text-therapy-calm font-medium'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                }`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => {
                    setSelectedModalities((prev) =>
                      prev.includes(m.value)
                        ? prev.filter((v) => v !== m.value)
                        : [...prev, m.value]
                    )
                  }}
                  className="accent-therapy-calm"
                />
                {m.label}
              </label>
            )
          })}
        </div>

        {/* Other onboarding-collected fields — read-only */}
        {(profile.tone || profile.message_length_preference || profile.follow_up_frequency ||
          (profile.common_terminology && profile.common_terminology.length > 0) ||
          (profile.preferred_exercises && profile.preferred_exercises.length > 0)) && (
          <div className="mt-4 pt-4 border-t border-gray-100 space-y-2 text-sm">
            {profile.tone && (
              <div className="flex gap-3">
                <span className="text-gray-500 w-32 flex-shrink-0">סגנון:</span>
                <span className="text-gray-700">{profile.tone}</span>
              </div>
            )}
            {profile.message_length_preference && (
              <div className="flex gap-3">
                <span className="text-gray-500 w-32 flex-shrink-0">אורך הודעות:</span>
                <span className="text-gray-700">{profile.message_length_preference}</span>
              </div>
            )}
            {profile.common_terminology && profile.common_terminology.length > 0 && (
              <div className="flex gap-3">
                <span className="text-gray-500 w-32 flex-shrink-0">מושגים:</span>
                <div className="flex flex-wrap gap-1">
                  {profile.common_terminology.map((t, i) => (
                    <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs">{t}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Section 2: Twin Controls (editable) ── */}
      <div className="card space-y-6">
        <div>
          <h2 className="text-lg font-bold text-gray-800">כוונונים חיים</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            שינויים ישפיעו מיד על כל הסיכומים וההודעות הבאות
          </p>
        </div>

        {/* Tone warmth slider */}
        <SliderControl
          label="חמימות תקשורת"
          leftLabel="פורמלי"
          rightLabel="חמים"
          value={toneWarmth}
          onChange={setToneWarmth}
          valueLabels={WARMTH_LABELS}
        />

        {/* Directiveness slider */}
        <SliderControl
          label="רמת הכוונה"
          leftLabel="חקרני"
          rightLabel="מכוון"
          value={directiveness}
          onChange={setDirectiveness}
          valueLabels={DIRECTIVE_LABELS}
        />
      </div>

      {/* ── Section 3: Prohibitions ── */}
      <div className="card space-y-4">
        <div>
          <h2 className="text-lg font-bold text-gray-800">מגבלות — מה אסור ל-AI להגיד</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            הוסף כללים ברורים שה-AI צריך להימנע מהם בכל מקרה
          </p>
        </div>

        {/* Add prohibition */}
        <div className="flex gap-2">
          <input
            type="text"
            value={newProhibition}
            onChange={(e) => setNewProhibition(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addProhibition() } }}
            className="input-field flex-1"
            placeholder='לדוגמה: "אל תמליץ על תרופות"'
          />
          <button
            onClick={addProhibition}
            disabled={!newProhibition.trim()}
            className="btn-secondary flex items-center gap-1 disabled:opacity-50"
          >
            <PlusIcon className="h-4 w-4" />
            הוסף
          </button>
        </div>

        {/* Prohibition list */}
        {prohibitions.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">אין מגבלות מוגדרות</p>
        ) : (
          <ul className="space-y-2">
            {prohibitions.map((p, i) => (
              <li
                key={i}
                className="flex items-center gap-3 bg-red-50 border border-red-100 rounded-lg px-4 py-2"
              >
                <span className="text-red-500 text-sm font-medium flex-shrink-0">❌</span>
                <span className="text-sm text-gray-800 flex-1">{p}</span>
                <button
                  onClick={() => removeProhibition(i)}
                  className="text-gray-400 hover:text-red-600 flex-shrink-0"
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ── Section 4: Custom rules (free-text) ── */}
      <div className="card space-y-3">
        <div>
          <h2 className="text-lg font-bold text-gray-800">כללים מותאמים אישית</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            הוראות בשפה חופשית לבינה מלאכותית, סגנון, גישה, ודרך טיפול מועדפת בנושאים ספציפיים.
          </p>
        </div>
        <textarea
          value={customRules}
          onChange={(e) => setCustomRules(e.target.value)}
          className="input-field h-32 resize-none text-sm"
          placeholder="לדוגמה: &quot;תמיד כלול שאלה פתוחה בסוף כל הודעה. בנושאי פחד ממוות — הפנה לפסיכיאטר.&quot;"
        />
      </div>

      {/* ── Section 5: Professional credentials (editable) ── */}
      <div className="card space-y-4">
        <div>
          <h2 className="text-lg font-bold text-gray-800">פרטים מקצועיים</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            פרטים אלו משולבים בהנחיות ה-AI ומשפיעים על אופן יצירת הסיכומים וההודעות
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Education */}
          <div className="space-y-1">
            <label className="block text-sm font-medium text-gray-700">השכלה</label>
            <input
              type="text"
              value={education}
              onChange={(e) => setEducation(e.target.value)}
              className="input-field"
              placeholder="לדוגמה: M.A. פסיכולוגיה קלינית, האוניברסיטה העברית"
            />
          </div>

          {/* Years of experience */}
          <div className="space-y-1">
            <label className="block text-sm font-medium text-gray-700">שנות ניסיון</label>
            <input
              type="text"
              value={yearsOfExperience}
              onChange={(e) => setYearsOfExperience(e.target.value)}
              className="input-field"
              placeholder="לדוגמה: 8"
            />
          </div>
        </div>

        {/* Certifications */}
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">הסמכות ותעודות</label>
          <input
            type="text"
            value={certifications}
            onChange={(e) => setCertifications(e.target.value)}
            className="input-field"
            placeholder="לדוגמה: מטפל מוסמך CBT, הסמכת EMDR"
          />
        </div>

        {/* Areas of expertise */}
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">תחומי התמחות</label>
          <textarea
            value={areasOfExpertise}
            onChange={(e) => setAreasOfExpertise(e.target.value)}
            className="input-field h-20 resize-none text-sm"
            placeholder="לדוגמה: חרדה, טראומה, יחסים זוגיים, הפרעות אכילה"
          />
        </div>
      </div>

      {/* ── Save / Reset bar ── */}
      <div className="sticky bottom-4">
        <div className="card bg-white shadow-lg border border-gray-200">
          <div className="flex items-center justify-between gap-4">
            <div className="text-sm">
              {saveSuccess && (
                <div className="flex items-center gap-2 text-green-700">
                  <CheckCircleIcon className="h-5 w-5" />
                  <span>נשמר בהצלחה! שינויים ישפיעו על כל קריאות ה-AI הבאות.</span>
                </div>
              )}
              {saveError && (
                <div className="flex items-center gap-2 text-red-700">
                  <ExclamationTriangleIcon className="h-5 w-5" />
                  <span>{saveError}</span>
                </div>
              )}
              {!saveSuccess && !saveError && isDirty && (
                <span className="text-amber-600 font-medium">יש שינויים שלא נשמרו</span>
              )}
              {!saveSuccess && !saveError && !isDirty && (
                <span className="text-gray-400 text-xs">גרסת סגנון {profile.style_version}</span>
              )}
            </div>

            <div className="flex items-center gap-3 flex-shrink-0">
              <button
                onClick={handleSave}
                disabled={!isDirty || saving}
                className="btn-primary flex items-center gap-2 disabled:opacity-50"
              >
                {saving ? (
                  <>
                    <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
                    שומר...
                  </>
                ) : (
                  'שמור שינויים'
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
