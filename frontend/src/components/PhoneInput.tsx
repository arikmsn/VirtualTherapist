/**
 * PhoneInput — country code dropdown + local number field.
 * Emits E.164 strings (e.g. "+972501234567") via onChange.
 * Accepts an E.164 string as `value` and splits it into code + local on init.
 */

import { useState, useEffect } from 'react'

interface CountryCode {
  code: string  // e.g. '+972'
  flag: string  // e.g. '🇮🇱'
  name: string  // e.g. 'ישראל'
}

// Israel first, USA second, then alphabetical by Hebrew name
const COUNTRY_CODES: CountryCode[] = [
  { code: '+972', flag: '🇮🇱', name: 'ישראל' },
  { code: '+1',   flag: '🇺🇸', name: 'ארה״ב' },
  { code: '+39',  flag: '🇮🇹', name: 'איטליה' },
  { code: '+43',  flag: '🇦🇹', name: 'אוסטריה' },
  { code: '+61',  flag: '🇦🇺', name: 'אוסטרליה' },
  { code: '+380', flag: '🇺🇦', name: 'אוקראינה' },
  { code: '+54',  flag: '🇦🇷', name: 'ארגנטינה' },
  { code: '+44',  flag: '🇬🇧', name: 'בריטניה' },
  { code: '+55',  flag: '🇧🇷', name: 'ברזיל' },
  { code: '+49',  flag: '🇩🇪', name: 'גרמניה' },
  { code: '+27',  flag: '🇿🇦', name: 'דרום אפריקה' },
  { code: '+31',  flag: '🇳🇱', name: 'הולנד' },
  { code: '+91',  flag: '🇮🇳', name: 'הודו' },
  { code: '+90',  flag: '🇹🇷', name: 'טורקיה' },
  { code: '+81',  flag: '🇯🇵', name: 'יפן' },
  { code: '+82',  flag: '🇰🇷', name: 'קוריאה' },
  { code: '+52',  flag: '🇲🇽', name: 'מקסיקו' },
  { code: '+20',  flag: '🇪🇬', name: 'מצרים' },
  { code: '+47',  flag: '🇳🇴', name: 'נורווגיה' },
  { code: '+86',  flag: '🇨🇳', name: 'סין' },
  { code: '+34',  flag: '🇪🇸', name: 'ספרד' },
  { code: '+33',  flag: '🇫🇷', name: 'צרפת' },
  { code: '+48',  flag: '🇵🇱', name: 'פולין' },
  { code: '+7',   flag: '🇷🇺', name: 'רוסיה' },
  { code: '+46',  flag: '🇸🇪', name: 'שוודיה' },
  { code: '+41',  flag: '🇨🇭', name: 'שווייץ' },
  { code: '+66',  flag: '🇹🇭', name: 'תאילנד' },
]

// Sorted longest-first so +380 matches before +38 etc.
const CODES_BY_LENGTH = [...COUNTRY_CODES].sort((a, b) => b.code.length - a.code.length)

function parseE164(e164: string): { countryCode: string; localNumber: string } {
  if (!e164 || !e164.startsWith('+')) {
    return { countryCode: '+972', localNumber: e164 ?? '' }
  }
  for (const c of CODES_BY_LENGTH) {
    if (e164.startsWith(c.code)) {
      return { countryCode: c.code, localNumber: e164.slice(c.code.length) }
    }
  }
  // Unrecognised country code — keep as-is under +972 display
  return { countryCode: '+972', localNumber: e164.slice(1) }
}

interface PhoneInputProps {
  value: string                        // E.164 or empty string
  onChange: (e164: string) => void
  required?: boolean
  className?: string                   // Applied to the wrapper div
  placeholder?: string                 // Local-number placeholder (default: '501234567')
  disabled?: boolean
}

export default function PhoneInput({
  value,
  onChange,
  required,
  className,
  placeholder = '501234567',
  disabled,
}: PhoneInputProps) {
  const [countryCode, setCountryCode] = useState('+972')
  const [localNumber, setLocalNumber] = useState('')

  // Parse incoming E.164 value into code + local
  useEffect(() => {
    const parsed = parseE164(value)
    setCountryCode(parsed.countryCode)
    setLocalNumber(parsed.localNumber)
  }, [value])

  function handleCodeChange(code: string) {
    setCountryCode(code)
    const local = localNumber.replace(/^0+/, '')
    onChange(local ? code + local : '')
  }

  function handleLocalChange(raw: string) {
    // Keep only digits, strip leading zeros
    const digits = raw.replace(/\D/g, '').replace(/^0+/, '')
    setLocalNumber(digits)
    onChange(digits ? countryCode + digits : '')
  }

  return (
    <div className={`flex ${className ?? ''}`} dir="ltr">
      <select
        value={countryCode}
        onChange={(e) => handleCodeChange(e.target.value)}
        disabled={disabled}
        className="border border-gray-300 rounded-l-lg px-2 py-2 text-sm bg-gray-50 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm min-w-[100px]"
      >
        {COUNTRY_CODES.map((c) => (
          <option key={c.code} value={c.code}>
            {c.flag} {c.code}
          </option>
        ))}
      </select>
      <input
        type="tel"
        value={localNumber}
        onChange={(e) => handleLocalChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        className="flex-1 border border-l-0 border-gray-300 rounded-r-lg px-3 py-2 text-sm focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
        dir="ltr"
      />
    </div>
  )
}
