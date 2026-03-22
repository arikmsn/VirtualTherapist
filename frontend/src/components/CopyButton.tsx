import { useState } from 'react'
import { ClipboardDocumentIcon, CheckIcon } from '@heroicons/react/24/outline'
import { strings } from '@/i18n/he'

interface Props {
  text: string
  className?: string
}

/**
 * Small "copy to clipboard" button used next to AI document headings.
 * Shows a brief "הועתק" confirmation for 2 seconds after a successful copy.
 */
export default function CopyButton({ text, className = '' }: Props) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Fallback for browsers where clipboard API requires explicit user gesture
      const el = document.createElement('textarea')
      el.value = text
      el.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={copied ? strings.copyButton.tooltip_copied : strings.copyButton.tooltip_copy}
      className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg border transition-colors ${
        copied
          ? 'bg-green-50 border-green-300 text-green-700'
          : 'bg-white border-gray-200 text-gray-500 hover:text-gray-700 hover:border-gray-300'
      } ${className}`}
    >
      {copied ? (
        <>
          <CheckIcon className="h-3.5 w-3.5 flex-shrink-0" />
          {strings.copyButton.label_copied}
        </>
      ) : (
        <>
          <ClipboardDocumentIcon className="h-3.5 w-3.5 flex-shrink-0" />
          {strings.copyButton.label_copy}
        </>
      )}
    </button>
  )
}
