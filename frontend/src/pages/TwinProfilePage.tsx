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
import {
  PROFESSION_OPTIONS,
  THERAPY_MODES,
  encodeProfession,
  decodeProfession,
  encodeModes,
  decodeModes,
  modeLabel,
} from '@/lib/therapistConstants'

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
  // Account creation date (for "days since signup" tile)
  therapist_created_at: string | null
  // Profession + therapy modes (migration 029)
  profession: string | null
  primary_therapy_modes: string[]   // API guarantees [] not null
  // Derived: CBT active for this therapist
  cbt_active: boolean
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
  const [tone, setTone] = useState('')
  const [newProhibition, setNewProhibition] = useState('')

  // Profession (decoded into key + free text)
  const [professionKey, setProfessionKey] = useState('')
  const [professionOtherText, setProfessionOtherText] = useState('')

  // Therapeutic modalities (decoded keys + free text for "other")
  const [selectedModalities, setSelectedModalities] = useState<string[]>([])
  const [modesOtherText, setModesOtherText] = useState('')

  // Professional credentials
  const [education, setEducation] = useState('')
  const [certifications, setCertifications] = useState('')
  const [yearsOfExperience, setYearsOfExperience] = useState('')
  const [areasOfExpertise, setAreasOfExpertise] = useState('')

  // Signature profile ("מה למדנו")
  const [sigProfile, setSigProfile] = useState<{
    is_active: boolean
    approved_sample_count: number
    min_samples_required: number
    samples_until_active: number
    style_summary: string | null
    style_version: number
    last_updated_at: string | null
  } | null>(null)

  // Save state
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState('')

  const isDirty =
    profile !== null && (
      toneWarmth !== profile.tone_warmth ||
      directiveness !== profile.directiveness ||
      customRules !== (profile.custom_rules || '') ||
      tone !== (profile.tone || '') ||
      JSON.stringify(prohibitions) !== JSON.stringify(profile.prohibitions || []) ||
      encodeProfession(professionKey, professionOtherText) !== (profile.profession || '') ||
      JSON.stringify([...encodeModes(selectedModalities, modesOtherText)].sort()) !==
        JSON.stringify([...(profile.primary_therapy_modes || [])].sort()) ||
      education !== (profile.education || '') ||
      certifications !== (profile.certifications || '') ||
      yearsOfExperience !== (profile.years_of_experience || '') ||
      areasOfExpertise !== (profile.areas_of_expertise || '')
    )

  useEffect(() => {
    const load = async () => {
      try {
        const [data, sig] = await Promise.allSettled([
          therapistAPI.getProfile() as Promise<TherapistProfile>,
          therapistAPI.getSignatureProfile(),
        ])
        if (sig.status === 'fulfilled') setSigProfile(sig.value)
        if (data.status === 'rejected') throw data.reason
        const d = (data as PromiseFulfilledResult<TherapistProfile>).value
        setProfile(d)
        setToneWarmth(d.tone_warmth)
        setDirectiveness(d.directiveness)
        setProhibitions(d.prohibitions || [])
        setCustomRules(d.custom_rules || '')
        setTone(d.tone || '')
        setEducation(d.education || '')
        setCertifications(d.certifications || '')
        setYearsOfExperience(d.years_of_experience || '')
        setAreasOfExpertise(d.areas_of_expertise || '')

        // Decode profession
        const { key, otherText } = decodeProfession(d.profession)
        setProfessionKey(key)
        setProfessionOtherText(otherText)

        // Decode therapy modes
        const { modes, otherText: mOther } = decodeModes(d.primary_therapy_modes || [])
        setSelectedModalities(modes)
        setModesOtherText(mOther)
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
      const encodedProfession = encodeProfession(professionKey, professionOtherText)
      const encodedModes = encodeModes(selectedModalities, modesOtherText)
      const updated = await therapistAPI.updateTwinControls({
        tone_warmth: toneWarmth,
        directiveness,
        prohibitions,
        custom_rules: customRules || null,
        tone: tone || null,
        profession: encodedProfession || null,
        primary_therapy_modes: encodedModes.length > 0 ? encodedModes : null,
        approach_description: encodedModes.length > 0 ? encodedModes.join(', ') : null,
        education: education || null,
        certifications: certifications || null,
        years_of_experience: yearsOfExperience || null,
        areas_of_expertise: areasOfExpertise || null,
      })
      setProfile(updated)
      // Re-sync decoded states to match the saved profile
      const { key, otherText } = decodeProfession(updated.profession)
      setProfessionKey(key)
      setProfessionOtherText(otherText)
      const { modes, otherText: mOther } = decodeModes(updated.primary_therapy_modes || [])
      setSelectedModalities(modes)
      setModesOtherText(mOther)
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

  const toggleMode = (value: string) => {
    setSelectedModalities((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    )
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
      <div className="flex items-center gap-2">
        <SparklesIcon className="h-6 w-6 text-therapy-calm" />
        <h1 className="text-2xl font-bold text-gray-900">פרופיל ה-Twin שלי</h1>
      </div>
      <p className="text-gray-600 mt-1 text-sm">
        כך ה-AI מדמה את הסגנון הטיפולי שלך — ערוך וכוון לפי הצורך
      </p>

      {/* ── "מה למדנו" — Signature Learning Overview ── */}
      {sigProfile && (
        <div className="card border-indigo-100 bg-indigo-50">
          <div className="flex items-center gap-2 mb-3">
            <SparklesIcon className="h-5 w-5 text-indigo-500" />
            <h2 className="text-base font-bold text-indigo-900">מה למדנו עליך</h2>
            {sigProfile.is_active ? (
              <span className="text-xs bg-indigo-600 text-white px-2 py-0.5 rounded-full mr-auto">
                מנגנון פעיל
              </span>
            ) : (
              <span className="text-xs bg-gray-300 text-gray-600 px-2 py-0.5 rounded-full mr-auto">
                {sigProfile.samples_until_active > 0
                  ? `עוד ${sigProfile.samples_until_active} סיכומים לפעילה`
                  : 'בהמתנה להפעלה'}
              </span>
            )}
          </div>

          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-white rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-indigo-700">{sigProfile.approved_sample_count}</div>
              <div className="text-xs text-gray-500 mt-0.5">סיכומים מאושרים</div>
            </div>
            <div className="bg-white rounded-lg p-3 text-center">
              <div className={`text-2xl font-bold ${sigProfile.samples_until_active === 0 ? 'text-green-600' : 'text-amber-600'}`}>
                {sigProfile.samples_until_active === 0 ? '✓' : sigProfile.samples_until_active}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">טרם מולאו</div>
            </div>
            <div className="bg-white rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-indigo-700">
                {profile.therapist_created_at
                  ? Math.floor((Date.now() - new Date(profile.therapist_created_at).getTime()) / 86400000)
                  : '—'}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">ימי פעילות</div>
            </div>
          </div>

          {/* Style summary — shown only when available */}
          {sigProfile.style_summary ? (
            <div>
              <div className="text-xs font-medium text-indigo-700 mb-1.5">סיכום הסגנון הנלמד:</div>
              <p className="text-sm text-indigo-900 leading-relaxed whitespace-pre-line bg-white rounded-lg p-3 border border-indigo-100">
                {sigProfile.style_summary}
              </p>
            </div>
          ) : !sigProfile.is_active ? (
            /* Only show "more samples needed" when NOT yet active */
            <p className="text-sm text-indigo-600 bg-white rounded-lg p-3 border border-indigo-100">
              {sigProfile.samples_until_active > 0
                ? `אשר עוד ${sigProfile.samples_until_active} סיכומים כדי להפעיל את מנגנון הלמידה.`
                : 'המנגנון עומד להיות מופעל — אשר את הסיכום הבא.'}
            </p>
          ) : null}

          {/* How it affects */}
          <div className="mt-4 pt-3 border-t border-indigo-200">
            <div className="text-xs font-medium text-indigo-700 mb-2">איך זה משפיע על ה-AI:</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {[
                { label: 'סיכומי פגישות', desc: 'AI כותב בסגנון ובמבנה שלך' },
                { label: 'הודעות למטופלים', desc: 'טון וניסוח מותאמים אישית' },
                { label: 'תדריך הכנה לפגישה', desc: 'מוצג במינוח שמוכר לך' },
                { label: 'תוכנית טיפולית', desc: 'גישה טיפולית ומטרות מותאמות' },
              ].map((item) => (
                <div key={item.label} className="flex items-start gap-2 bg-white rounded-lg p-2.5 border border-indigo-100">
                  <CheckCircleIcon className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
                  <div>
                    <div className="text-xs font-medium text-gray-800">{item.label}</div>
                    <div className="text-xs text-gray-500">{item.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Context note ── */}
      <div className="text-xs text-gray-500 bg-gray-50 rounded-xl px-4 py-3 leading-relaxed border border-gray-100">
        המקצוע וגישות הטיפול שלך מאפשרים ל-Twin להתאים את מבנה הסיכומים, השפה הקלינית וניתוח הפגישות —
        לדוגמה, CBT מפעיל ניתוח מחשבות אוטומטיות ומטלות בין-מפגשים, בעוד מטפל פסיכודינמי יקבל מבנה שונה.
        {profile.cbt_active && (
          <span className="mr-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">
            ✓ CBT פעיל — חבילת CBT מופעלת על כל הסיכומים
          </span>
        )}
      </div>

      {/* ── Unified Professional Details card (profession + modalities + credentials) ── */}
      <div className="card space-y-6">
        <div>
          <h2 className="text-lg font-bold text-gray-800">פרטים מקצועיים</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            פרטים אלו משולבים בהנחיות ה-AI ומשפיעים על אופן יצירת הסיכומים וההודעות
          </p>
        </div>

        {/* Profession grid */}
        <div className="space-y-2">
          <div className="text-sm font-medium text-gray-700">מקצוע</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {PROFESSION_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setProfessionKey(opt.value)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors ${
                  professionKey === opt.value
                    ? 'border-therapy-calm bg-blue-50 text-therapy-calm font-medium'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                }`}
              >
                <span>{opt.emoji}</span>
                <span>{opt.label}</span>
              </button>
            ))}
          </div>
          {professionKey === 'other' && (
            <input
              type="text"
              value={professionOtherText}
              onChange={(e) => setProfessionOtherText(e.target.value)}
              placeholder="פרט את תפקידך המקצועי..."
              className="input-field mt-2"
              autoFocus
            />
          )}
        </div>

        <div className="border-t border-gray-100" />

        {/* Therapy modes multi-select */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-700">גישות טיפוליות</span>
            {profile.cbt_active && (
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">
                CBT פעיל
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400">בחר את כל השיטות הטיפוליות בהן אתה עובד (בחירה מרובה)</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {THERAPY_MODES.map((m) => {
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
                    onChange={() => toggleMode(m.value)}
                    className="accent-therapy-calm"
                  />
                  {m.label}
                </label>
              )
            })}
          </div>
          {selectedModalities.includes('other') && (
            <input
              type="text"
              value={modesOtherText}
              onChange={(e) => setModesOtherText(e.target.value)}
              placeholder="פרט גישה טיפולית נוספת..."
              className="input-field mt-2"
            />
          )}
          {selectedModalities.length === 0 && (
            <p className="text-xs text-gray-400">לא נבחרו גישות טיפוליות</p>
          )}
          {selectedModalities.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-1">
              {selectedModalities.map((v) => (
                <span key={v} className="px-2.5 py-0.5 bg-blue-50 border border-blue-200 text-therapy-calm text-xs rounded-full font-medium">
                  {modeLabel(v === 'other' && modesOtherText ? `other:${modesOtherText}` : v)}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="border-t border-gray-100" />

        {/* Credentials */}
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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

        {/* Tone (onboarding-collected, editable) */}
        <div className="border-t border-gray-100 pt-4 space-y-3 text-sm">
          <div className="flex gap-3 items-center">
            <span className="text-gray-500 w-32 flex-shrink-0">סגנון:</span>
            <input
              type="text"
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-therapy-calm/30 text-gray-700"
              placeholder="לדוגמה: חמה ותומכת"
            />
          </div>
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
      </div>

      {/* ── Twin Controls (editable sliders) ── */}
      <div className="card space-y-6">
        <div>
          <h2 className="text-lg font-bold text-gray-800">כוונונים חיים</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            שינויים ישפיעו מיד על כל הסיכומים וההודעות הבאות
          </p>
        </div>

        <SliderControl
          label="חמימות תקשורת"
          leftLabel="פורמלי"
          rightLabel="חמים"
          value={toneWarmth}
          onChange={setToneWarmth}
          valueLabels={WARMTH_LABELS}
        />

        <SliderControl
          label="רמת הכוונה"
          leftLabel="חקרני"
          rightLabel="מכוון"
          value={directiveness}
          onChange={setDirectiveness}
          valueLabels={DIRECTIVE_LABELS}
        />
      </div>

      {/* ── Prohibitions ── */}
      <div className="card space-y-4">
        <div>
          <h2 className="text-lg font-bold text-gray-800">מגבלות — מה אסור ל-AI להגיד</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            הוסף כללים ברורים שה-AI צריך להימנע מהם בכל מקרה
          </p>
        </div>

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

      {/* ── Custom rules (free-text) ── */}
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

      {/* ── Save bar ── */}
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
                <span className="text-gray-400 text-xs">כל השינויים נשמרו</span>
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
