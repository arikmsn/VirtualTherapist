/**
 * Professional Settings Page (formerly "Twin Profile")
 *
 * Two inner tabs:
 *   Tab 1 — הגדרות מקצועיות טיפוליות
 *     a. פרטים מקצועיים  (profession, approaches, credentials)
 *     b. דגימות עבודה    (example summary + example message from onboarding)
 *     c. פרוטוקולים טיפוליים מועדפים  (system + custom protocol library)
 *     d. מידע מצטבר      (stats: approved samples, active days)
 *
 *   Tab 2 — הגדרות בינה מלאכותית
 *     a. מה למדנו עליך   (signature profile)
 *     b. כוונונים חיים   (warmth + directiveness sliders)
 *     c. מגבלות          (prohibitions list)
 *     d. כללים מותאמים   (custom rules textarea)
 *
 * URL: /twin  (unchanged — just the label in the nav changed)
 */

import { useState, useEffect } from 'react'
import {
  SparklesIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  PlusIcon,
  XMarkIcon,
  BriefcaseIcon,
  CpuChipIcon,
  PencilSquareIcon,
  TrashIcon,
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

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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
  example_summaries: string[] | null
  example_messages: string[] | null
  onboarding_completed: boolean
  onboarding_step: number
  tone_warmth: number
  directiveness: number
  prohibitions: string[]
  custom_rules: string | null
  style_version: number
  education: string | null
  certifications: string | null
  years_of_experience: string | null
  areas_of_expertise: string | null
  therapist_created_at: string | null
  profession: string | null
  primary_therapy_modes: string[]
  cbt_active: boolean
  protocols_used: string[]
  custom_protocols: ProtocolItem[]
}

interface ProtocolItem {
  id: string
  name: string
  approach_id: string
  target_problem: string
  description: string
  typical_sessions: number | null
  core_techniques: string[]
  is_system: boolean
  is_used: boolean
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const WARMTH_LABELS: Record<number, string> = {
  1: 'פורמלי מאוד', 2: 'פורמלי', 3: 'מאוזן', 4: 'חמים', 5: 'חמים מאוד',
}
const DIRECTIVE_LABELS: Record<number, string> = {
  1: 'חקרני מאוד', 2: 'חקרני', 3: 'מאוזן', 4: 'מכוון', 5: 'מכוון מאוד',
}

// ---------------------------------------------------------------------------
// Shared sub-components
// ---------------------------------------------------------------------------

function SliderControl({
  label, leftLabel, rightLabel, value, onChange, valueLabels,
}: {
  label: string; leftLabel: string; rightLabel: string
  value: number; onChange: (v: number) => void; valueLabels: Record<number, string>
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
          type="range" min={1} max={5} step={1} value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-therapy-calm"
        />
        <span className="text-xs text-gray-400 w-16 text-right">{rightLabel}</span>
      </div>
      <div className="flex justify-between px-[72px]">
        {[1, 2, 3, 4, 5].map((v) => (
          <div key={v} className={`text-xs text-center w-5 ${value === v ? 'text-therapy-calm font-bold' : 'text-gray-300'}`}>
            {v}
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Protocol Library sub-components
// ---------------------------------------------------------------------------

const BLANK_CUSTOM: Omit<ProtocolItem, 'id' | 'is_system' | 'is_used'> = {
  name: '',
  approach_id: 'other',
  target_problem: '',
  description: '',
  typical_sessions: null,
  core_techniques: [],
}

function CustomProtocolModal({
  initial,
  onSave,
  onClose,
}: {
  initial?: Partial<ProtocolItem>
  onSave: (data: Omit<ProtocolItem, 'id' | 'is_system' | 'is_used'>) => Promise<void>
  onClose: () => void
}) {
  const [form, setForm] = useState({
    ...BLANK_CUSTOM,
    ...(initial ?? {}),
  })
  const [techniqueInput, setTechniqueInput] = useState('')
  const [saving, setSaving] = useState(false)

  const addTechnique = () => {
    const t = techniqueInput.trim()
    if (!t || form.core_techniques.includes(t)) return
    setForm((f) => ({ ...f, core_techniques: [...f.core_techniques, t] }))
    setTechniqueInput('')
  }

  const removeTechnique = (t: string) =>
    setForm((f) => ({ ...f, core_techniques: f.core_techniques.filter((x) => x !== t) }))

  const handleSave = async () => {
    if (!form.name.trim() || !form.target_problem.trim() || !form.description.trim()) return
    setSaving(true)
    try {
      await onSave({
        name: form.name.trim(),
        approach_id: form.approach_id,
        target_problem: form.target_problem.trim(),
        description: form.description.trim(),
        typical_sessions: form.typical_sessions,
        core_techniques: form.core_techniques,
      })
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" dir="rtl">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-base font-bold text-gray-800">
            {initial?.id ? 'עריכת פרוטוקול מותאם' : 'פרוטוקול חדש'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
        <div className="px-5 py-4 space-y-4">
          <div className="space-y-1">
            <label className="text-sm font-medium text-gray-700">שם הפרוטוקול *</label>
            <input
              className="input-field"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="לדוגמה: CBT לחרדת ביצוע"
            />
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium text-gray-700">גישה טיפולית</label>
            <select
              className="input-field"
              value={form.approach_id}
              onChange={(e) => setForm((f) => ({ ...f, approach_id: e.target.value }))}
            >
              {THERAPY_MODES.filter((m) => m.value !== 'other').map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
              <option value="other">אחר</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium text-gray-700">בעיה / אינדיקציה *</label>
            <input
              className="input-field"
              value={form.target_problem}
              onChange={(e) => setForm((f) => ({ ...f, target_problem: e.target.value }))}
              placeholder="לדוגמה: חרדת ביצוע, פרפקציוניזם"
            />
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium text-gray-700">תיאור קצר *</label>
            <textarea
              className="input-field h-20 resize-none text-sm"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="תיאור הגישה, מטרות, ומהלך הטיפול..."
            />
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium text-gray-700">מספר פגישות אופייני</label>
            <input
              type="number" min={1} max={100}
              className="input-field"
              value={form.typical_sessions ?? ''}
              onChange={(e) => setForm((f) => ({
                ...f, typical_sessions: e.target.value ? Number(e.target.value) : null,
              }))}
              placeholder="לדוגמה: 12"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">טכניקות ליבה</label>
            <div className="flex gap-2">
              <input
                className="input-field flex-1"
                value={techniqueInput}
                onChange={(e) => setTechniqueInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTechnique() } }}
                placeholder="הוסף טכניקה ולחץ Enter"
              />
              <button
                onClick={addTechnique}
                disabled={!techniqueInput.trim()}
                className="btn-secondary flex items-center gap-1 disabled:opacity-50"
              >
                <PlusIcon className="h-4 w-4" />
              </button>
            </div>
            {form.core_techniques.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {form.core_techniques.map((t) => (
                  <span key={t} className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-blue-50 border border-blue-200 text-therapy-calm text-xs rounded-full">
                    {t}
                    <button onClick={() => removeTechnique(t)} className="hover:text-red-500">
                      <XMarkIcon className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-gray-100">
          <button onClick={onClose} className="btn-secondary">ביטול</button>
          <button
            onClick={handleSave}
            disabled={saving || !form.name.trim() || !form.target_problem.trim() || !form.description.trim()}
            className="btn-primary disabled:opacity-50"
          >
            {saving ? 'שומר...' : 'שמור פרוטוקול'}
          </button>
        </div>
      </div>
    </div>
  )
}

function ProtocolCard({
  protocol,
  onToggleUsed,
  onEdit,
  onDelete,
}: {
  protocol: ProtocolItem
  onToggleUsed: () => void
  onEdit?: () => void
  onDelete?: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className={`rounded-xl border p-3 transition-colors ${
      protocol.is_used ? 'border-blue-200 bg-blue-50' : 'border-gray-200 bg-white'
    }`}>
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={protocol.is_used}
          onChange={onToggleUsed}
          className="mt-1 accent-therapy-calm h-4 w-4 cursor-pointer flex-shrink-0"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-sm font-semibold ${protocol.is_used ? 'text-blue-900' : 'text-gray-800'}`}>
              {protocol.name}
            </span>
            {!protocol.is_system && (
              <span className="text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full">מותאם אישית</span>
            )}
            {protocol.typical_sessions && (
              <span className="text-xs text-gray-400">{protocol.typical_sessions} פגישות</span>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-0.5">{protocol.target_problem}</p>

          {expanded && (
            <div className="mt-2 space-y-1.5">
              <p className="text-xs text-gray-700 leading-relaxed">{protocol.description}</p>
              {protocol.core_techniques.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {protocol.core_techniques.map((t) => (
                    <span key={t} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{t}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-therapy-calm hover:underline mt-1"
          >
            {expanded ? 'פחות' : 'פרטים'}
          </button>
        </div>

        {!protocol.is_system && onEdit && onDelete && (
          <div className="flex gap-1.5 flex-shrink-0">
            <button onClick={onEdit} className="text-gray-400 hover:text-blue-600 p-1">
              <PencilSquareIcon className="h-4 w-4" />
            </button>
            <button onClick={onDelete} className="text-gray-400 hover:text-red-600 p-1">
              <TrashIcon className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 1 — הגדרות מקצועיות טיפוליות
// ---------------------------------------------------------------------------

function ProfessionalTab({
  profile,
  sigProfile,
  // editable state — lifted from parent for unified save
  professionKey, setProfessionKey,
  professionOtherText, setProfessionOtherText,
  selectedModalities, toggleMode,
  modesOtherText, setModesOtherText,
  education, setEducation,
  certifications, setCertifications,
  yearsOfExperience, setYearsOfExperience,
  areasOfExpertise, setAreasOfExpertise,
  tone, setTone,
}: {
  profile: TherapistProfile
  sigProfile: { approved_sample_count: number; is_active: boolean; samples_until_active: number } | null
  professionKey: string; setProfessionKey: (v: string) => void
  professionOtherText: string; setProfessionOtherText: (v: string) => void
  selectedModalities: string[]; toggleMode: (v: string) => void
  modesOtherText: string; setModesOtherText: (v: string) => void
  education: string; setEducation: (v: string) => void
  certifications: string; setCertifications: (v: string) => void
  yearsOfExperience: string; setYearsOfExperience: (v: string) => void
  areasOfExpertise: string; setAreasOfExpertise: (v: string) => void
  tone: string; setTone: (v: string) => void
}) {
  // --- Protocol library local state ---
  const [protocols, setProtocols] = useState<ProtocolItem[]>([])
  const [protocolsLoading, setProtocolsLoading] = useState(false)
  const [showCustomModal, setShowCustomModal] = useState(false)
  const [editingProtocol, setEditingProtocol] = useState<ProtocolItem | null>(null)
  const [protocolFilter, setProtocolFilter] = useState<'all' | 'used'>('all')
  const [protocolSaveStatus, setProtocolSaveStatus] = useState<'idle' | 'saved'>('idle')

  useEffect(() => {
    setProtocolsLoading(true)
    therapistAPI.getProtocols()
      .then((data) => setProtocols(data.protocols))
      .catch(() => {/* non-critical */})
      .finally(() => setProtocolsLoading(false))
  }, [])

  const handleToggleUsed = async (protocol: ProtocolItem) => {
    const newUsed = protocol.is_used
      ? protocols.filter((p) => p.is_used && p.id !== protocol.id).map((p) => p.id)
      : [...protocols.filter((p) => p.is_used).map((p) => p.id), protocol.id]

    setProtocols((prev) => prev.map((p) => p.id === protocol.id ? { ...p, is_used: !p.is_used } : p))
    try {
      await therapistAPI.updateProtocolsUsed(newUsed)
      setProtocolSaveStatus('saved')
      setTimeout(() => setProtocolSaveStatus('idle'), 2000)
    } catch {
      // revert on error
      setProtocols((prev) => prev.map((p) => p.id === protocol.id ? { ...p, is_used: protocol.is_used } : p))
    }
  }

  const handleCreateCustom = async (data: Omit<ProtocolItem, 'id' | 'is_system' | 'is_used'>) => {
    const created = await therapistAPI.createCustomProtocol(data)
    setProtocols((prev) => [...prev, created])
  }

  const handleUpdateCustom = async (id: string, data: Omit<ProtocolItem, 'id' | 'is_system' | 'is_used'>) => {
    const updated = await therapistAPI.updateCustomProtocol(id, data)
    setProtocols((prev) => prev.map((p) => p.id === id ? { ...p, ...updated } : p))
  }

  const handleDeleteCustom = async (id: string) => {
    if (!confirm('למחוק פרוטוקול זה?')) return
    await therapistAPI.deleteCustomProtocol(id)
    setProtocols((prev) => prev.filter((p) => p.id !== id))
  }

  const visibleProtocols = protocolFilter === 'used'
    ? protocols.filter((p) => p.is_used)
    : protocols

  return (
    <div className="space-y-6">

      {/* ── א. פרטים מקצועיים ── */}
      <div className="card space-y-6">
        <div>
          <h2 className="text-lg font-bold text-gray-800">פרטים מקצועיים</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            המקצוע והגישות הטיפוליות משפיעים על מבנה הסיכומים, השפה הקלינית ותוכניות הטיפול
          </p>
        </div>

        {/* Profession grid */}
        <div className="space-y-2">
          <div className="text-sm font-medium text-gray-700">מקצוע</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
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
                <span className="text-right">{opt.label}</span>
              </button>
            ))}
          </div>
          {professionKey === 'other' && (
            <input
              type="text" value={professionOtherText}
              onChange={(e) => setProfessionOtherText(e.target.value)}
              placeholder="פרט את תפקידך המקצועי..."
              className="input-field mt-2" autoFocus
            />
          )}
        </div>

        <div className="border-t border-gray-100" />

        {/* Therapy modes multi-select */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-700">גישות טיפוליות</span>
            {profile.cbt_active && (
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">CBT פעיל</span>
            )}
          </div>
          <p className="text-xs text-gray-400">בחר את כל השיטות הטיפוליות בהן אתה עובד (בחירה מרובה)</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {THERAPY_MODES.map((m) => {
              const checked = selectedModalities.includes(m.value)
              return (
                <div key={m.value}>
                  <label className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors text-sm ${
                    checked ? 'border-therapy-calm bg-blue-50 text-therapy-calm font-medium' : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                  }`}>
                    <input
                      type="checkbox" checked={checked}
                      onChange={() => toggleMode(m.value)}
                      className="accent-therapy-calm"
                    />
                    {m.label}
                  </label>
                  {m.description && checked && (
                    <p className="text-xs text-gray-500 mt-1 pr-2 leading-relaxed">{m.description}</p>
                  )}
                </div>
              )
            })}
          </div>
          {selectedModalities.includes('other') && (
            <input
              type="text" value={modesOtherText}
              onChange={(e) => setModesOtherText(e.target.value)}
              placeholder="פרט גישה טיפולית נוספת..." className="input-field mt-2"
            />
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
              <input type="text" value={education} onChange={(e) => setEducation(e.target.value)}
                className="input-field" placeholder="לדוגמה: M.A. פסיכולוגיה קלינית" />
            </div>
            <div className="space-y-1">
              <label className="block text-sm font-medium text-gray-700">שנות ניסיון</label>
              <input type="text" value={yearsOfExperience} onChange={(e) => setYearsOfExperience(e.target.value)}
                className="input-field" placeholder="לדוגמה: 8" />
            </div>
          </div>
          <div className="space-y-1">
            <label className="block text-sm font-medium text-gray-700">הסמכות ותעודות</label>
            <input type="text" value={certifications} onChange={(e) => setCertifications(e.target.value)}
              className="input-field" placeholder="לדוגמה: מטפל מוסמך CBT, הסמכת EMDR" />
          </div>
          <div className="space-y-1">
            <label className="block text-sm font-medium text-gray-700">תחומי התמחות</label>
            <textarea value={areasOfExpertise} onChange={(e) => setAreasOfExpertise(e.target.value)}
              className="input-field h-20 resize-none text-sm"
              placeholder="לדוגמה: חרדה, טראומה, יחסים זוגיים" />
          </div>
          <div className="space-y-1">
            <label className="block text-sm font-medium text-gray-700">סגנון</label>
            <input type="text" value={tone} onChange={(e) => setTone(e.target.value)}
              className="input-field" placeholder="לדוגמה: חמה ותומכת" />
          </div>
        </div>
      </div>

      {/* ── ב. דגימות עבודה ── */}
      {(profile.example_summaries?.length || profile.example_messages?.length) ? (
        <div className="card space-y-4">
          <div>
            <h2 className="text-lg font-bold text-gray-800">דגימות עבודה</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              דגימות אלו (שהוזנו בהגדרה הראשונית) עוזרות ל-AI ללמוד את הסגנון שלך
            </p>
          </div>
          {profile.example_summaries?.[0] && (
            <div className="space-y-1.5">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">דוגמת סיכום פגישה</div>
              <p className="text-sm text-gray-700 leading-relaxed bg-gray-50 rounded-lg p-3 whitespace-pre-line">
                {profile.example_summaries[0].slice(0, 400)}{profile.example_summaries[0].length > 400 ? '…' : ''}
              </p>
            </div>
          )}
          {profile.example_messages?.[0] && (
            <div className="space-y-1.5">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">דוגמת הודעה למטופל</div>
              <p className="text-sm text-gray-700 leading-relaxed bg-gray-50 rounded-lg p-3 whitespace-pre-line">
                {profile.example_messages[0].slice(0, 300)}{profile.example_messages[0].length > 300 ? '…' : ''}
              </p>
            </div>
          )}
        </div>
      ) : null}

      {/* ── ג. פרוטוקולים טיפוליים מועדפים ── */}
      <div className="card space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-gray-800">פרוטוקולים טיפוליים מועדפים</h2>
              {protocolSaveStatus === 'saved' && (
                <span className="text-xs text-green-600 font-medium">נשמר ✓</span>
              )}
            </div>
            <p className="text-sm text-gray-500 mt-0.5">
              סמנו את הפרוטוקולים שאתם עובדים איתם, המערכת תתאים את הסיכומים ותוכניות הטיפול בהתאם
            </p>
          </div>
          <button
            onClick={() => setShowCustomModal(true)}
            className="btn-secondary flex items-center gap-1.5 flex-shrink-0 text-sm"
          >
            <PlusIcon className="h-4 w-4" />
            פרוטוקול מותאם
          </button>
        </div>

        {/* Filter toggle */}
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
          {(['all', 'used'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setProtocolFilter(f)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                protocolFilter === f ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {f === 'all' ? 'כל הפרוטוקולים' : `בשימוש (${protocols.filter((p) => p.is_used).length})`}
            </button>
          ))}
        </div>

        {protocolsLoading ? (
          <div className="text-sm text-gray-400 text-center py-6">טוען פרוטוקולים...</div>
        ) : visibleProtocols.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">
            {protocolFilter === 'used' ? 'לא נבחרו פרוטוקולים עדיין' : 'אין פרוטוקולים'}
          </p>
        ) : (
          <div className="space-y-2">
            {visibleProtocols.map((p) => (
              <ProtocolCard
                key={p.id}
                protocol={p}
                onToggleUsed={() => handleToggleUsed(p)}
                onEdit={p.is_system ? undefined : () => setEditingProtocol(p)}
                onDelete={p.is_system ? undefined : () => handleDeleteCustom(p.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Modals */}
      {showCustomModal && (
        <CustomProtocolModal
          onSave={handleCreateCustom}
          onClose={() => setShowCustomModal(false)}
        />
      )}
      {editingProtocol && (
        <CustomProtocolModal
          initial={editingProtocol}
          onSave={(data) => handleUpdateCustom(editingProtocol.id, data)}
          onClose={() => setEditingProtocol(null)}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 2 — הגדרות בינה מלאכותית
// ---------------------------------------------------------------------------

function AISettingsTab({
  profile,
  sigProfile,
  toneWarmth, setToneWarmth,
  directiveness, setDirectiveness,
  prohibitions, setProhibitions,
  customRules, setCustomRules,
}: {
  profile: TherapistProfile
  sigProfile: {
    is_active: boolean; approved_sample_count: number; min_samples_required: number
    samples_until_active: number; style_summary: string | null
    style_version: number; last_updated_at: string | null
  } | null
  toneWarmth: number; setToneWarmth: (v: number) => void
  directiveness: number; setDirectiveness: (v: number) => void
  prohibitions: string[]; setProhibitions: (v: string[]) => void
  customRules: string; setCustomRules: (v: string) => void
}) {
  const [newProhibition, setNewProhibition] = useState('')

  const addProhibition = () => {
    const t = newProhibition.trim()
    if (!t || prohibitions.includes(t)) return
    setProhibitions([...prohibitions, t])
    setNewProhibition('')
  }

  const removeProhibition = (idx: number) =>
    setProhibitions(prohibitions.filter((_, i) => i !== idx))

  return (
    <div className="space-y-6">

      {/* ── א. מה למדנו עליך ── */}
      {sigProfile && (
        <div className="card border-indigo-100 bg-indigo-50">
          <div className="flex items-center gap-2 mb-3">
            <SparklesIcon className="h-5 w-5 text-indigo-500" />
            <h2 className="text-base font-bold text-indigo-900">מה למדנו עליך</h2>
            {sigProfile.is_active ? (
              <span className="text-xs bg-indigo-600 text-white px-2 py-0.5 rounded-full mr-auto">מנגנון פעיל</span>
            ) : (
              <span className="text-xs bg-gray-300 text-gray-600 px-2 py-0.5 rounded-full mr-auto">
                {sigProfile.samples_until_active > 0
                  ? `עוד ${sigProfile.samples_until_active} סיכומים לפעילה`
                  : 'בהמתנה להפעלה'}
              </span>
            )}
          </div>

          <p className="text-xs text-indigo-700 mb-3 leading-relaxed">
            ה-AI לומד את הסגנון שלך מתוך המקצוע, הגישות הטיפוליות, הפרוטוקולים ודגימות העבודה שהגדרת — בשילוב עם
            הסיכומים שאישרת.
          </p>

          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-white rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-indigo-700">{sigProfile.approved_sample_count}</div>
              <div className="text-xs text-gray-500 mt-0.5">סיכומים מאושרים</div>
            </div>
            <div className="bg-white rounded-lg p-3 text-center">
              <div className={`text-2xl font-bold ${sigProfile.samples_until_active === 0 ? 'text-green-600' : 'text-amber-600'}`}>
                {sigProfile.samples_until_active === 0 ? '✓' : sigProfile.samples_until_active}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">
                {sigProfile.samples_until_active === 0 ? 'מינימום הושג' : 'נדרשים עוד'}
              </div>
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

          {sigProfile.style_summary ? (
            <div>
              <div className="text-xs font-medium text-indigo-700 mb-1.5">סיכום הסגנון הנלמד:</div>
              <p className="text-sm text-indigo-900 leading-relaxed whitespace-pre-line bg-white rounded-lg p-3 border border-indigo-100">
                {sigProfile.style_summary}
              </p>
            </div>
          ) : !sigProfile.is_active && sigProfile.samples_until_active > 0 ? (
            <p className="text-sm text-indigo-600 bg-white rounded-lg p-3 border border-indigo-100">
              {`אשר עוד ${sigProfile.samples_until_active} סיכומים כדי להפעיל את מנגנון הלמידה.`}
            </p>
          ) : null}

          <div className="mt-4 pt-3 border-t border-indigo-200">
            <div className="text-xs font-medium text-indigo-700 mb-2">איך זה משפיע על ה-AI:</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {[
                { label: 'סיכומי פגישות', desc: 'AI כותב בסגנון ובמבנה שלך' },
                { label: 'הודעות למטופלים', desc: 'טון וניסוח מותאמים אישית' },
                { label: 'תדריך הכנה לפגישה', desc: 'מוצג במינוח שמוכר לך' },
                { label: 'תוכנית טיפולית', desc: 'גישה ומטרות מותאמות לפרוטוקול' },
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

      {profile.cbt_active && (
        <div className="text-xs text-blue-700 bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 leading-relaxed">
          ✓ CBT פעיל — חבילת ניתוח CBT מופעלת על כל הסיכומים, סיכומי העומק ותוכניות הטיפול.
        </div>
      )}

      {/* ── ב. כוונונים חיים ── */}
      <div className="card space-y-6">
        <div>
          <h2 className="text-lg font-bold text-gray-800">כוונונים חיים</h2>
          <p className="text-sm text-gray-500 mt-0.5">שינויים ישפיעו מיד על כל הסיכומים וההודעות הבאות</p>
        </div>
        <SliderControl
          label="חמימות תקשורת" leftLabel="פורמלי" rightLabel="חמים"
          value={toneWarmth} onChange={setToneWarmth} valueLabels={WARMTH_LABELS}
        />
        <SliderControl
          label="רמת הכוונה" leftLabel="חקרני" rightLabel="מכוון"
          value={directiveness} onChange={setDirectiveness} valueLabels={DIRECTIVE_LABELS}
        />
      </div>

      {/* ── ג. מגבלות ── */}
      <div className="card space-y-4">
        <div>
          <h2 className="text-lg font-bold text-gray-800">מגבלות — מה אסור ל-AI להגיד</h2>
          <p className="text-sm text-gray-500 mt-0.5">הוסף כללים ברורים שה-AI צריך להימנע מהם בכל מקרה</p>
        </div>
        <div className="flex gap-2">
          <input
            type="text" value={newProhibition}
            onChange={(e) => setNewProhibition(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addProhibition() } }}
            className="input-field flex-1"
            placeholder='לדוגמה: "אל תמליץ על תרופות"'
          />
          <button
            onClick={addProhibition} disabled={!newProhibition.trim()}
            className="btn-secondary flex items-center gap-1 disabled:opacity-50"
          >
            <PlusIcon className="h-4 w-4" /> הוסף
          </button>
        </div>
        {prohibitions.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">אין מגבלות מוגדרות</p>
        ) : (
          <ul className="space-y-2">
            {prohibitions.map((p, i) => (
              <li key={i} className="flex items-center gap-3 bg-red-50 border border-red-100 rounded-lg px-4 py-2">
                <span className="text-red-500 text-sm font-medium flex-shrink-0">❌</span>
                <span className="text-sm text-gray-800 flex-1">{p}</span>
                <button onClick={() => removeProhibition(i)} className="text-gray-400 hover:text-red-600 flex-shrink-0">
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ── ד. כללים מותאמים אישית ── */}
      <div className="card space-y-3">
        <div>
          <h2 className="text-lg font-bold text-gray-800">כללים מותאמים אישית</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            הוראות בשפה חופשית לבינה מלאכותית — סגנון, גישה, ודרך טיפול מועדפת בנושאים ספציפיים
          </p>
        </div>
        <textarea
          value={customRules} onChange={(e) => setCustomRules(e.target.value)}
          className="input-field h-32 resize-none text-sm"
          placeholder='לדוגמה: "תמיד כלול שאלה פתוחה בסוף כל הודעה. בנושאי פחד ממוות — הפנה לפסיכיאטר."'
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

type SettingsTab = 'professional' | 'ai'

export default function TwinProfilePage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('professional')

  const [profile, setProfile] = useState<TherapistProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // --- Professional tab state (lifted here for unified save) ---
  const [professionKey, setProfessionKey] = useState('')
  const [professionOtherText, setProfessionOtherText] = useState('')
  const [selectedModalities, setSelectedModalities] = useState<string[]>([])
  const [modesOtherText, setModesOtherText] = useState('')
  const [education, setEducation] = useState('')
  const [certifications, setCertifications] = useState('')
  const [yearsOfExperience, setYearsOfExperience] = useState('')
  const [areasOfExpertise, setAreasOfExpertise] = useState('')
  const [tone, setTone] = useState('')

  // --- AI tab state ---
  const [toneWarmth, setToneWarmth] = useState(3)
  const [directiveness, setDirectiveness] = useState(3)
  const [prohibitions, setProhibitions] = useState<string[]>([])
  const [customRules, setCustomRules] = useState('')

  const [sigProfile, setSigProfile] = useState<{
    is_active: boolean; approved_sample_count: number; min_samples_required: number
    samples_until_active: number; style_summary: string | null
    style_version: number; last_updated_at: string | null
  } | null>(null)

  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState('')

  const isDirty = profile !== null && (
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
        if (data.status === 'rejected') throw (data as PromiseRejectedResult).reason
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
        const { key, otherText } = decodeProfession(d.profession)
        setProfessionKey(key)
        setProfessionOtherText(otherText)
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
      const { key, otherText } = decodeProfession(updated.profession)
      setProfessionKey(key); setProfessionOtherText(otherText)
      const { modes, otherText: mOther } = decodeModes(updated.primary_therapy_modes || [])
      setSelectedModalities(modes); setModesOtherText(mOther)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err: any) {
      setSaveError(err.response?.data?.detail || 'שגיאה בשמירה')
    } finally {
      setSaving(false)
    }
  }

  const toggleMode = (value: string) =>
    setSelectedModalities((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    )

  // --- Loading / Error ---

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" dir="rtl">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-therapy-calm mx-auto mb-4" />
          <p className="text-gray-600">טוען הגדרות...</p>
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
        <BriefcaseIcon className="h-6 w-6 text-therapy-calm" />
        <h1 className="text-2xl font-bold text-gray-900">הגדרות מקצועיות</h1>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
        <button
          onClick={() => setActiveTab('professional')}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'professional' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <BriefcaseIcon className="h-4 w-4" />
          הגדרות מקצועיות טיפוליות
        </button>
        <button
          onClick={() => setActiveTab('ai')}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'ai' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <CpuChipIcon className="h-4 w-4" />
          הגדרות בינה מלאכותית
        </button>
      </div>

      {/* Tab content */}
      {activeTab === 'professional' ? (
        <ProfessionalTab
          profile={profile}
          sigProfile={sigProfile}
          professionKey={professionKey} setProfessionKey={setProfessionKey}
          professionOtherText={professionOtherText} setProfessionOtherText={setProfessionOtherText}
          selectedModalities={selectedModalities} toggleMode={toggleMode}
          modesOtherText={modesOtherText} setModesOtherText={setModesOtherText}
          education={education} setEducation={setEducation}
          certifications={certifications} setCertifications={setCertifications}
          yearsOfExperience={yearsOfExperience} setYearsOfExperience={setYearsOfExperience}
          areasOfExpertise={areasOfExpertise} setAreasOfExpertise={setAreasOfExpertise}
          tone={tone} setTone={setTone}
        />
      ) : (
        <AISettingsTab
          profile={profile}
          sigProfile={sigProfile}
          toneWarmth={toneWarmth} setToneWarmth={setToneWarmth}
          directiveness={directiveness} setDirectiveness={setDirectiveness}
          prohibitions={prohibitions} setProhibitions={setProhibitions}
          customRules={customRules} setCustomRules={setCustomRules}
        />
      )}

      {/* Sticky save bar */}
      <div className="sticky bottom-4">
        <div className="card bg-white shadow-lg border border-gray-200">
          <div className="flex items-center justify-between gap-4">
            <div className="text-sm">
              {saveSuccess && (
                <div className="flex items-center gap-2 text-green-700">
                  <CheckCircleIcon className="h-5 w-5" />
                  <span>נשמר! שינויים ישפיעו על כל קריאות ה-AI הבאות.</span>
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
            <button
              onClick={handleSave}
              disabled={!isDirty || saving}
              className="btn-primary flex items-center gap-2 disabled:opacity-50 flex-shrink-0"
            >
              {saving ? (
                <><span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />שומר...</>
              ) : 'שמור שינויים'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
