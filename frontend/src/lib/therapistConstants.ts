/**
 * Canonical therapist profession and therapy modes lists.
 * Used in both OnboardingPage and TwinProfilePage to ensure consistency.
 *
 * Storage pattern for "Other":
 *   - profession: "other:free text" (e.g. "other:פסיכואנליסט")
 *   - therapy modes: array containing "other:free text" (e.g. ["cbt", "other:פסיכואנליזה"])
 */

export interface ProfessionOption {
  value: string
  label: string
  emoji: string
}

export interface TherapyModeOption {
  value: string
  label: string
  description?: string   // tooltip / help text (OT approaches and future modes)
}

export const PROFESSION_OPTIONS: ProfessionOption[] = [
  { value: 'psychologist', label: 'פסיכולוג/ית קליני/ת', emoji: '🧠' },
  { value: 'clinical_social_worker', label: 'עו״ס קליני/ת', emoji: '🤝' },
  { value: 'psychiatrist', label: 'פסיכיאטר/ית', emoji: '⚕️' },
  { value: 'family_therapist', label: 'מטפל/ת זוגי-משפחתי', emoji: '👨‍👩‍👧' },
  { value: 'art_therapist', label: 'מטפל/ת באמנויות', emoji: '🎨' },
  { value: 'occupational_therapist', label: 'מרפא/ת בעיסוק', emoji: '🖐️' },
  { value: 'coach', label: 'מאמן/ת רגשי/התנהגותי', emoji: '🌱' },
  { value: 'counselor', label: 'יועץ/ת רגשי/ת', emoji: '💬' },
  { value: 'other', label: 'אחר', emoji: '➕' },
]

export const THERAPY_MODES: TherapyModeOption[] = [
  { value: 'cbt', label: 'CBT — קוגניטיבי-התנהגותי' },
  { value: 'psychodynamic', label: 'פסיכודינמי' },
  { value: 'act', label: 'ACT — קבלה ומחויבות' },
  { value: 'dbt', label: 'DBT — דיאלקטי-התנהגותי' },
  { value: 'humanistic', label: 'הומניסטי' },
  { value: 'family_systemic', label: 'משפחתי/מערכתי' },
  { value: 'psychodrama', label: 'פסיכודרמה' },
  { value: 'integrative', label: 'אינטגרטיבי' },
  { value: 'emdr', label: 'EMDR' },
  {
    value: 'ot_functional',
    label: 'ריפוי בעיסוק — גישה תפקודית',
    description:
      'מיפוי תפקוד בעיסוקים יומיומיים (לבוש, רחצה, כתיבה, עבודה, לימודים) והגדרת מטרות שיפור השתתפות בהתאם לסביבה ולתפקידים של המטופל.',
  },
  {
    value: 'ot_sensory',
    label: 'ריפוי בעיסוק — אינטגרציה חושית',
    description:
      'עבודה על ויסות חושי ומוטורי, התאמת סביבה ופעילויות לילדים ומבוגרים עם קשיי קשב, ויסות, אוטיזם או רגישות יתר/חסר לגירויים (מגע, רעש, תנועה).',
  },
  { value: 'other', label: 'אחר' },
]

// ---------------------------------------------------------------------------
// Profession encode / decode
// ---------------------------------------------------------------------------

/**
 * Encode a profession key + optional free text into the storage string.
 * e.g. encodeProfession('other', 'פסיכואנליסט') → 'other:פסיכואנליסט'
 *      encodeProfession('psychologist', '') → 'psychologist'
 */
export function encodeProfession(key: string, otherText: string): string {
  if (key === 'other' && otherText.trim()) {
    return `other:${otherText.trim()}`
  }
  return key
}

/**
 * Decode a stored profession string into key + free text.
 * e.g. decodeProfession('other:פסיכואנליסט') → { key: 'other', otherText: 'פסיכואנליסט' }
 *      decodeProfession('psychologist') → { key: 'psychologist', otherText: '' }
 *      decodeProfession(null) → { key: '', otherText: '' }
 */
export function decodeProfession(stored: string | null): { key: string; otherText: string } {
  if (!stored) return { key: '', otherText: '' }
  if (stored.startsWith('other:')) {
    return { key: 'other', otherText: stored.slice('other:'.length) }
  }
  return { key: stored, otherText: '' }
}

/**
 * Human-readable label for a stored profession string.
 * e.g. professionLabel('other:פסיכואנליסט') → 'פסיכואנליסט'
 *      professionLabel('psychologist') → 'פסיכולוג/ית קליני/ת'
 */
export function professionLabel(stored: string | null): string {
  if (!stored) return ''
  if (stored.startsWith('other:')) return stored.slice('other:'.length)
  const opt = PROFESSION_OPTIONS.find((o) => o.value === stored)
  return opt ? opt.label : stored
}

// ---------------------------------------------------------------------------
// Therapy modes encode / decode
// ---------------------------------------------------------------------------

/**
 * Encode the selected mode keys + optional free text for "other".
 * Replaces any bare 'other' entry with 'other:text'.
 */
export function encodeModes(modes: string[], otherText: string): string[] {
  return modes.map((m) => {
    if (m === 'other' || m.startsWith('other:')) {
      return otherText.trim() ? `other:${otherText.trim()}` : 'other'
    }
    return m
  })
}

/**
 * Decode an array of stored mode strings into clean keys + other free text.
 * e.g. ['cbt', 'other:פסיכואנליזה'] → { modes: ['cbt', 'other'], otherText: 'פסיכואנליזה' }
 */
export function decodeModes(storedModes: string[]): { modes: string[]; otherText: string } {
  let otherText = ''
  const modes = storedModes.map((m) => {
    if (m.startsWith('other:')) {
      otherText = m.slice('other:'.length)
      return 'other'
    }
    return m
  })
  return { modes, otherText }
}

/**
 * Human-readable label for a single stored mode value.
 * e.g. modeLabel('other:פסיכואנליזה') → 'פסיכואנליזה'
 *      modeLabel('cbt') → 'CBT — קוגניטיבי-התנהגותי'
 */
export function modeLabel(stored: string): string {
  if (stored.startsWith('other:')) return stored.slice('other:'.length)
  const opt = THERAPY_MODES.find((m) => m.value === stored)
  return opt ? opt.label : stored
}
