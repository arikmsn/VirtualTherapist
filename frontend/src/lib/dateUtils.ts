/**
 * Date formatting helpers for Israeli therapist UI.
 *
 * Single source of truth — import from here instead of calling
 * toLocaleDateString / toLocaleString inline throughout the app.
 *
 * Israel convention: DD.MM.YY with 24-hour time (HH:mm).
 * The locale parameter is reserved for future therapist_locale support.
 */

/** Format a YYYY-MM-DD string (or any ISO string) to DD.MM.YY */
export function formatDateIL(dateStr: string): string {
  // Append noon to prevent DST / timezone from shifting the calendar date
  const d = new Date(dateStr.length === 10 ? dateStr + 'T12:00:00' : dateStr)
  if (isNaN(d.getTime())) return dateStr
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const yy = String(d.getFullYear()).slice(-2)
  return `${dd}.${mm}.${yy}`
}

/**
 * Format an ISO timestamp to DD.MM.YY HH:mm.
 * Strings without a timezone suffix are treated as UTC (backend convention).
 */
export function formatDatetimeIL(isoStr: string | null | undefined): string {
  if (!isoStr) return ''
  // Parse as UTC if no timezone suffix (backend returns naive UTC strings)
  const iso =
    isoStr.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(isoStr)
      ? isoStr
      : isoStr + 'Z'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const yy = String(d.getFullYear()).slice(-2)
  const hh = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${dd}.${mm}.${yy} ${hh}:${min}`
}
