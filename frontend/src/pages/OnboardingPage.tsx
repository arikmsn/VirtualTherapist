import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { agentAPI, therapistAPI } from '@/lib/api'
import { useAuth } from '@/auth/useAuth'
import { CheckIcon } from '@heroicons/react/24/solid'
import AppLogo from '@/components/common/AppLogo'
import { strings } from '@/i18n/he'
import {
  PROFESSION_OPTIONS,
  THERAPY_MODES,
  encodeProfession,
  encodeModes,
} from '@/lib/therapistConstants'

const DRAFT_KEY = 'metapel_setup_draft'

// TODO: consider merging Step 0 (Profession) and Step 1 (Therapy Modes) into a single screen.
// Both are button-grid selectors. On desktop they would fit comfortably; on mobile (~360px)
// the combined grid (~18 options) would require scrolling. Leave separate for now.
const STEPS = [
  { title: strings.onboarding.step_profession_title, description: strings.onboarding.step_profession_description },
  { title: strings.onboarding.step_modes_title, description: strings.onboarding.step_modes_description },
  { title: strings.onboarding.step_style_title, description: strings.onboarding.step_style_description },
  { title: strings.onboarding.step_background_title, description: strings.onboarding.step_background_description },
  { title: strings.onboarding.step_examples_title, description: strings.onboarding.step_examples_description },
]

const TONE_OPTIONS = [
  strings.onboarding.tone_formal,
  strings.onboarding.tone_professional_accessible,
  strings.onboarding.tone_friendly,
  strings.onboarding.tone_direct,
  strings.onboarding.tone_empathetic,
]

export default function OnboardingPage() {
  const navigate = useNavigate()
  const { markOnboardingComplete, logout } = useAuth()
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const [form, setForm] = useState({
    profession: '',
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
  const [selectedModes, setSelectedModes] = useState<string[]>([])
  const [professionOtherText, setProfessionOtherText] = useState('')
  const [modesOtherText, setModesOtherText] = useState('')

  // Restore draft from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY)
      if (!raw) return
      const draft = JSON.parse(raw)
      if (draft.form) setForm((prev) => ({ ...prev, ...draft.form }))
      if (draft.selectedTones) setSelectedTones(draft.selectedTones)
      if (draft.selectedModes) setSelectedModes(draft.selectedModes)
      if (draft.professionOtherText) setProfessionOtherText(draft.professionOtherText)
      if (draft.modesOtherText) setModesOtherText(draft.modesOtherText)
      if (typeof draft.step === 'number') setStep(draft.step)
    } catch { /* corrupt draft — ignore */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Save draft to localStorage whenever form state changes
  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({
        step, form, selectedTones, selectedModes, professionOtherText, modesOtherText,
      }))
    } catch { /* storage full — ignore */ }
  }, [step, form, selectedTones, selectedModes, professionOtherText, modesOtherText])

  const set = (field: keyof typeof form, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }))

  const toggleTone = (tone: string) =>
    setSelectedTones((prev) =>
      prev.includes(tone) ? prev.filter((t) => t !== tone) : [...prev, tone]
    )

  const toggleMode = (mode: string) =>
    setSelectedModes((prev) =>
      prev.includes(mode) ? prev.filter((m) => m !== mode) : [...prev, mode]
    )

  // Combines chip selections + free-text extra into a single tone string for the backend
  const buildToneString = () =>
    [...selectedTones, form.toneExtra].filter(Boolean).join(', ')

  const canAdvance = (): boolean => {
    if (step === 0) return form.profession !== '' && (form.profession !== 'other' || professionOtherText.trim() !== '')
    if (step === 1) return selectedModes.length > 0 && (!selectedModes.includes('other') || modesOtherText.trim() !== '')
    if (step === 2) return selectedTones.length > 0 || form.toneExtra.trim() !== ''
    return true
  }

  const handleNext = async () => {
    if (!canAdvance()) return
    setSaving(true)
    setError('')
    try {
      if (step === 0) {
        // TODO: verify if profession is used downstream before removing.
        // Currently stored in therapist_profiles.profession but NOT injected into
        // any AI system prompt or logic — only returned in the profile API response.
        await therapistAPI.updateTwinControls({
          profession: encodeProfession(form.profession, professionOtherText),
        })
      } else if (step === 1) {
        // Save therapy modes — also populate legacy approach field for backward compat
        const encodedModes = encodeModes(selectedModes, modesOtherText)
        const firstMode = encodedModes[0] || 'other'
        await Promise.all([
          agentAPI.completeOnboardingStep(1, { approach: firstMode, approachDescription: '' }),
          therapistAPI.updateTwinControls({
            primary_therapy_modes: encodedModes,
            approach_description: encodedModes.join(', '),
          }),
        ])
      } else if (step === 2) {
        await agentAPI.completeOnboardingStep(2, {
          tone: buildToneString(),
          messageLength: form.messageLength,
          terminology: form.terminology,
        })
      } else if (step === 3) {
        // All four fields below ARE used in AI system prompt (agent.py lines 260-263).
        // education, certifications, years_of_experience, areas_of_expertise are all injected.
        await therapistAPI.updateTwinControls({
          education: form.education || null,
          certifications: form.certifications || null,
          years_of_experience: form.yearsOfExperience || null,
          areas_of_expertise: form.areasOfExpertise || null,
        })
      } else if (step === 4) {
        // Optional examples step — only save if provided
        if (form.exampleSummary || form.exampleMessage) {
          await agentAPI.completeOnboardingStep(5, {
            exampleSummary: form.exampleSummary,
            exampleMessage: form.exampleMessage,
          })
        }
        // Mark onboarding complete on the backend
        await therapistAPI.completeOnboarding()
        localStorage.removeItem(DRAFT_KEY)
        markOnboardingComplete()
        navigate('/dashboard', { replace: true })
        return
      }
      setStep((s) => s + 1)
    } catch {
      setError(strings.onboarding.error_save)
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
            {strings.onboarding.exit_button}
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

            {/* Step 1 — Profession */}
            {step === 0 && (
              <div className="space-y-3">
                <p className="text-xs text-gray-400 bg-indigo-50 rounded-lg px-3 py-2 leading-relaxed">
                  {strings.onboarding.profession_hint}
                </p>
                <div className="grid grid-cols-2 gap-2.5">
                  {PROFESSION_OPTIONS.map((p) => (
                    <button
                      key={p.value}
                      type="button"
                      onClick={() => set('profession', p.value)}
                      className={`flex items-center gap-2.5 px-4 py-3 rounded-xl border-2 text-sm font-medium transition-colors text-right ${
                        form.profession === p.value
                          ? 'border-indigo-500 bg-indigo-50 text-indigo-800 ring-2 ring-indigo-200'
                          : 'border-gray-200 bg-white text-gray-700 hover:border-indigo-200 hover:bg-indigo-50/30'
                      }`}
                    >
                      <span className="text-lg leading-none">{p.emoji}</span>
                      <span className="flex-1">{p.label}</span>
                      {form.profession === p.value && (
                        <span className="text-indigo-500 text-xs font-bold">✓</span>
                      )}
                    </button>
                  ))}
                </div>
                {form.profession === 'other' && (
                  <input
                    type="text"
                    value={professionOtherText}
                    onChange={(e) => setProfessionOtherText(e.target.value)}
                    placeholder={strings.onboarding.profession_placeholder}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 mt-1"
                    autoFocus
                  />
                )}
              </div>
            )}

            {/* Step 2 — Therapy Modes */}
            {step === 1 && (
              <div className="space-y-3">
                <p className="text-xs text-gray-400 bg-indigo-50 rounded-lg px-3 py-2 leading-relaxed">
                  {strings.onboarding.modes_hint}
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {THERAPY_MODES.map((m) => {
                    const checked = selectedModes.includes(m.value)
                    return (
                      <button
                        key={m.value}
                        type="button"
                        onClick={() => toggleMode(m.value)}
                        className={`flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm transition-colors text-right ${
                          checked
                            ? 'border-indigo-500 bg-indigo-600 text-white font-medium'
                            : 'border-gray-200 bg-white text-gray-600 hover:border-indigo-300 hover:bg-indigo-50/30'
                        }`}
                      >
                        <span className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${checked ? 'bg-white border-white' : 'border-gray-300'}`}>
                          {checked && <span className="text-indigo-600 text-xs font-bold">✓</span>}
                        </span>
                        <span>{m.label}</span>
                      </button>
                    )
                  })}
                </div>
                {selectedModes.includes('other') && (
                  <input
                    type="text"
                    value={modesOtherText}
                    onChange={(e) => setModesOtherText(e.target.value)}
                    placeholder={strings.onboarding.modes_placeholder}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                    autoFocus
                  />
                )}
                {selectedModes.length === 0 ? (
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-amber-600">{strings.onboarding.modes_min_error}</p>
                    <button
                      type="button"
                      onClick={() => setSelectedModes(['integrative'])}
                      className="text-xs text-gray-400 underline hover:text-gray-600"
                    >
                      {strings.onboarding.modes_skip}
                    </button>
                  </div>
                ) : (
                  <p className="text-xs text-indigo-600 font-medium">{selectedModes.length} שיטות נבחרו</p>
                )}
              </div>
            )}

            {/* Step 3 — Writing Style */}
            {step === 2 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {strings.onboarding.tone_label} <span className="text-red-500">*</span>
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
                    placeholder={strings.onboarding.tone_placeholder}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    {strings.onboarding.length_label}
                  </label>
                  <div className="flex gap-3">
                    {[
                      { value: 'short', label: strings.onboarding.length_short },
                      { value: 'medium', label: strings.onboarding.length_medium },
                      { value: 'detailed', label: strings.onboarding.length_detailed },
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
                    {strings.onboarding.terminology_label}
                  </label>
                  <input
                    type="text"
                    value={form.terminology}
                    onChange={(e) => set('terminology', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                    placeholder={strings.onboarding.terminology_placeholder}
                  />
                </div>
              </div>
            )}

            {/* Step 4 — Professional Background */}
            {step === 3 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    {strings.onboarding.education_label}
                  </label>
                  <input
                    type="text"
                    value={form.education}
                    onChange={(e) => set('education', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                    placeholder={strings.onboarding.education_placeholder}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    {strings.onboarding.certifications_label}
                  </label>
                  <input
                    type="text"
                    value={form.certifications}
                    onChange={(e) => set('certifications', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                    placeholder={strings.onboarding.certifications_placeholder}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      {strings.onboarding.experience_label}
                    </label>
                    <input
                      type="text"
                      value={form.yearsOfExperience}
                      onChange={(e) => set('yearsOfExperience', e.target.value)}
                      className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                      placeholder={strings.onboarding.experience_placeholder}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      {strings.onboarding.specialties_label}
                    </label>
                    <input
                      type="text"
                      value={form.areasOfExpertise}
                      onChange={(e) => set('areasOfExpertise', e.target.value)}
                      className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                      placeholder={strings.onboarding.specialties_placeholder}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Step 5 — Learning Examples (optional) */}
            {step === 4 && (
              <div className="space-y-4">
                <p className="text-xs text-gray-400 bg-gray-50 rounded-lg p-3">
                  {strings.onboarding.examples_hint}
                </p>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    {strings.onboarding.example_summary_label}
                  </label>
                  <textarea
                    value={form.exampleSummary}
                    onChange={(e) => set('exampleSummary', e.target.value)}
                    rows={5}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
                    placeholder={strings.onboarding.example_summary_placeholder}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    {strings.onboarding.example_message_label}
                  </label>
                  <textarea
                    value={form.exampleMessage}
                    onChange={(e) => set('exampleMessage', e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
                    placeholder={strings.onboarding.example_message_placeholder}
                  />
                  <p className="mt-1.5 text-xs text-gray-400 leading-relaxed">
                    {strings.onboarding.example_message_hint}
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
              {strings.onboarding.back_button}
            </button>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleNext}
                disabled={saving || !canAdvance()}
                className="px-6 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {saving ? strings.onboarding.saving_button : step === STEPS.length - 1 ? strings.onboarding.complete_button : strings.onboarding.continue_button}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
