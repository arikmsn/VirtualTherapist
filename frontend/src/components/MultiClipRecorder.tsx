/**
 * MultiClipRecorder — multi-segment audio capture for Voice Recap.
 *
 * The therapist records any number of short clips per session.
 * Each clip is uploaded and transcribed immediately.
 * When done, "סיים ושלח לתמלול" merges the transcripts and triggers AI summary generation.
 */

import { useState, useRef, useCallback, useEffect } from 'react'
import {
  MicrophoneIcon,
  StopIcon,
  TrashIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import { sessionsAPI } from '@/lib/api'
import { strings } from '@/i18n/he'

interface Clip {
  id: number
  clip_index: number
  duration_seconds: number | null
  transcript: string | null
  status: string // pending | transcribed | error
}

const clipOrdinal = (n: number) => strings.multiClipRecorder.ordinals[n - 1] || `#${n}`

interface MultiClipRecorderProps {
  sessionId: number
  /** Called with merged transcript text — parent shows review modal before finalizing */
  onTranscriptReady: (mergedTranscript: string) => void
  /** Whether the parent is processing (finalizing in progress) */
  processing?: boolean
  disabled?: boolean
}

export default function MultiClipRecorder({
  sessionId,
  onTranscriptReady,
  processing = false,
  disabled = false,
}: MultiClipRecorderProps) {
  const [clips, setClips] = useState<Clip[]>([])
  const [recording, setRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [permissionError, setPermissionError] = useState('')
  const [uploadError, setUploadError] = useState('')

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const elapsedRef = useRef(0)

  // Load existing clips on mount (in case page was refreshed mid-session)
  useEffect(() => {
    sessionsAPI.listClips(sessionId).then(setClips).catch(() => {})
  }, [sessionId])

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  const startRecording = useCallback(async () => {
    setPermissionError('')
    setUploadError('')
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

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: mimeType })
        const duration = elapsedRef.current
        setUploading(true)
        try {
          const newClip = await sessionsAPI.uploadClip(sessionId, blob, duration)
          setClips((prev) => [...prev, newClip])
        } catch (err: unknown) {
          const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
          setUploadError(detail || strings.multiClipRecorder.error_upload)
        } finally {
          setUploading(false)
        }
      }

      recorder.start(1000)
      setRecording(true)
      setElapsed(0)
      elapsedRef.current = 0

      timerRef.current = setInterval(() => {
        elapsedRef.current += 1
        setElapsed((prev) => prev + 1)
      }, 1000)
    } catch (err: unknown) {
      const name = (err as { name?: string })?.name || ''
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        setPermissionError(strings.multiClipRecorder.error_mic_blocked)
      } else {
        setPermissionError(strings.multiClipRecorder.error_mic_generic)
      }
    }
  }, [sessionId])

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

  const handleDeleteClip = async (clipId: number) => {
    try {
      await sessionsAPI.deleteClip(sessionId, clipId)
      setClips((prev) =>
        prev
          .filter((c) => c.id !== clipId)
          .map((c, i) => ({ ...c, clip_index: i + 1 })),
      )
    } catch {
      // ignore
    }
  }

  const handleFinalize = () => {
    // Build merged transcript client-side so the parent can show a review modal
    const transcribed = clips.filter((c) => c.status === 'transcribed' && c.transcript)
    if (transcribed.length === 0) return
    const merged = transcribed
      .map((c) => `[קטע ${c.clip_index}]\n${c.transcript!.trim()}`)
      .join('\n\n')
    onTranscriptReady(merged)
  }

  const transcribedCount = clips.filter((c) => c.status === 'transcribed').length
  const canFinalize = transcribedCount > 0 && !recording && !uploading

  if (disabled) return null

  return (
    <div className="space-y-4">
      {/* Error messages */}
      {permissionError && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
          {permissionError}
        </div>
      )}
      {uploadError && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
          {uploadError}
        </div>
      )}

      {/* Clip list */}
      {clips.length > 0 && (
        <div className="space-y-2">
          {clips.map((clip) => (
            <div
              key={clip.id}
              className={`flex items-start gap-3 rounded-lg border p-3 text-sm ${
                clip.status === 'error'
                  ? 'border-red-200 bg-red-50'
                  : 'border-gray-200 bg-white'
              }`}
            >
              {/* Status icon */}
              <div className="mt-0.5 flex-shrink-0">
                {clip.status === 'transcribed' ? (
                  <CheckCircleIcon className="h-4 w-4 text-green-500" />
                ) : clip.status === 'error' ? (
                  <ExclamationCircleIcon className="h-4 w-4 text-red-500" />
                ) : (
                  <ArrowPathIcon className="h-4 w-4 animate-spin text-gray-400" />
                )}
              </div>

              {/* Clip info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 font-medium text-gray-800">
                  <span>קטע #{clip.clip_index}</span>
                  {clip.duration_seconds != null && (
                    <span className="font-mono text-xs text-gray-400">
                      {formatTime(clip.duration_seconds)}
                    </span>
                  )}
                </div>
                {clip.status === 'transcribed' && clip.transcript && (
                  <p className="mt-1 text-gray-500 text-xs line-clamp-2 leading-relaxed">
                    {clip.transcript}
                  </p>
                )}
                {clip.status === 'error' && (
                  <p className="mt-1 text-red-500 text-xs">{strings.multiClipRecorder.transcription_error}</p>
                )}
                {clip.status === 'pending' && (
                  <p className="mt-1 text-gray-400 text-xs">{strings.multiClipRecorder.transcription_pending}</p>
                )}
              </div>

              {/* Delete */}
              {!recording && !uploading && (
                <button
                  onClick={() => handleDeleteClip(clip.id)}
                  className="flex-shrink-0 text-gray-300 hover:text-red-500 transition-colors"
                  title={strings.multiClipRecorder.delete_clip_title}
                >
                  <TrashIcon className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Active recording indicator */}
      {recording && (
        <div className="flex items-center gap-4 bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500" />
            </span>
            <span className="text-red-700 font-medium text-sm">מקליט קטע {clipOrdinal(clips.length + 1)}...</span>
          </div>
          <span className="text-red-600 font-mono">{formatTime(elapsed)}</span>
          <div className="flex-1" />
          <button
            onClick={stopRecording}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
          >
            <StopIcon className="h-4 w-4" />
            {strings.multiClipRecorder.stop_clip_button}
          </button>
        </div>
      )}

      {/* Uploading indicator */}
      {uploading && (
        <div className="flex items-center gap-3 text-sm text-gray-600 bg-gray-50 border border-gray-200 rounded-lg p-3">
          <ArrowPathIcon className="h-4 w-4 animate-spin text-therapy-calm" />
          {strings.multiClipRecorder.uploading}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Record new clip */}
        {!recording && !uploading && (
          <button
            onClick={startRecording}
            disabled={processing}
            className="inline-flex items-center gap-2 px-4 py-2 bg-therapy-calm text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 text-sm"
          >
            <MicrophoneIcon className="h-4 w-4" />
            {clips.length === 0 ? strings.multiClipRecorder.record_first_button : strings.multiClipRecorder.record_more_button}
          </button>
        )}

        {/* Finalize — triggers transcript review modal in parent */}
        {canFinalize && (
          <button
            onClick={handleFinalize}
            disabled={processing}
            className="inline-flex items-center gap-2 px-5 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 text-sm font-medium"
          >
            {processing ? (
              <>
                <ArrowPathIcon className="h-4 w-4 animate-spin" />
                {strings.multiClipRecorder.finalize_processing}
              </>
            ) : (
              <>
                <CheckCircleIcon className="h-4 w-4" />
                {strings.multiClipRecorder.finalize_button} ({transcribedCount} קטעים)
              </>
            )}
          </button>
        )}
      </div>

      {/* Empty state hint */}
      {clips.length === 0 && !recording && !uploading && (
        <p className="text-xs text-gray-400 text-center">
          {strings.multiClipRecorder.idle_hint}
        </p>
      )}
    </div>
  )
}
