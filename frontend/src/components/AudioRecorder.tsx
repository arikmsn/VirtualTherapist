/**
 * AudioRecorder — browser-based audio capture for Voice Recap.
 *
 * Uses MediaRecorder API to record audio in the browser.
 * Outputs a Blob that can be uploaded to the backend for Whisper transcription.
 *
 * PRD reference: Feature 2 — Session Capture & Voice Recap
 */

import { useState, useRef, useCallback, useEffect } from 'react'
import { MicrophoneIcon, StopIcon, TrashIcon } from '@heroicons/react/24/outline'

interface AudioRecorderProps {
  /** Called with the recorded audio blob when user confirms the recording */
  onRecordingComplete: (blob: Blob) => void
  /** Whether the parent is currently processing (uploading/transcribing) */
  processing?: boolean
  /** Disable the recorder (e.g. when a summary already exists) */
  disabled?: boolean
}

export default function AudioRecorder({
  onRecordingComplete,
  processing = false,
  disabled = false,
}: AudioRecorderProps) {
  const [recording, setRecording] = useState(false)
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [permissionError, setPermissionError] = useState('')

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Cleanup object URLs on unmount
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl)
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [audioUrl])

  const startRecording = useCallback(async () => {
    setPermissionError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'

      const recorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = recorder
      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType })
        const url = URL.createObjectURL(blob)
        setAudioBlob(blob)
        setAudioUrl(url)
        // Stop all tracks to release the microphone
        stream.getTracks().forEach((t) => t.stop())
      }

      recorder.start(1000) // collect data every second
      setRecording(true)
      setElapsed(0)

      // Timer
      timerRef.current = setInterval(() => {
        setElapsed((prev) => prev + 1)
      }, 1000)
    } catch (err: any) {
      const name: string = err?.name || ''
      // Branch solely on the error name returned by getUserMedia.
      // navigator.permissions.query is NOT consulted — it reports inconsistent
      // states on iOS Safari and some Android browsers, causing false "blocked" messages.
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        setPermissionError('גישה למיקרופון נחסמה בדפדפן. יש לאפשר גישה בהגדרות הדפדפן ולרענן את הדף.')
      } else {
        // NotFoundError, NotReadableError, AbortError, OverconstrainedError, or unknown
        setPermissionError('לא הצלחנו להתחיל הקלטה. נסה שוב, או בדוק את המיקרופון והגדרות המכשיר.')
      }
    }
  }, [])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop()
      setRecording(false)
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
  }, [recording])

  const discardRecording = useCallback(() => {
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    setAudioBlob(null)
    setAudioUrl(null)
    setElapsed(0)
  }, [audioUrl])

  const handleSubmit = useCallback(() => {
    if (audioBlob) {
      onRecordingComplete(audioBlob)
    }
  }, [audioBlob, onRecordingComplete])

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  if (disabled) return null

  return (
    <div className="space-y-3">
      {permissionError && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
          {permissionError}
        </div>
      )}

      {/* Recording state */}
      {recording && (
        <div className="flex items-center gap-4 bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
            </span>
            <span className="text-red-700 font-medium">מקליט...</span>
          </div>
          <span className="text-red-600 font-mono text-lg">{formatTime(elapsed)}</span>
          <div className="flex-1" />
          <button
            onClick={stopRecording}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            <StopIcon className="h-5 w-5" />
            עצור הקלטה
          </button>
        </div>
      )}

      {/* Review state — audio recorded, not yet submitted */}
      {!recording && audioBlob && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-blue-700 font-medium">הקלטה מוכנה</span>
            <span className="text-blue-600 font-mono">{formatTime(elapsed)}</span>
          </div>

          {/* Playback */}
          {audioUrl && (
            <audio controls src={audioUrl} className="w-full" />
          )}

          <div className="flex items-center gap-3">
            <button
              onClick={handleSubmit}
              disabled={processing}
              className="btn-primary disabled:opacity-50 flex items-center gap-2"
            >
              {processing ? (
                <>
                  <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
                  מתמלל ויוצר סיכום...
                </>
              ) : (
                'תמלל וצור סיכום'
              )}
            </button>
            <button
              onClick={discardRecording}
              disabled={processing}
              className="flex items-center gap-2 text-gray-500 hover:text-red-600 text-sm disabled:opacity-50"
            >
              <TrashIcon className="h-4 w-4" />
              מחק והקלט מחדש
            </button>
          </div>
        </div>
      )}

      {/* Idle state — no recording yet */}
      {!recording && !audioBlob && (
        <div className="bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
          <p className="text-sm text-gray-500 mb-3">
            הקלט סיכום קולי קצר (1-2 דקות): מצב המטופל, התערבויות, תגובה, משימות, הערכת סיכון.
          </p>
          <button
            onClick={startRecording}
            disabled={processing}
            className="inline-flex items-center gap-2 px-6 py-3 bg-therapy-calm text-white rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            <MicrophoneIcon className="h-5 w-5" />
            התחל הקלטה קולית
          </button>
        </div>
      )}
    </div>
  )
}
