/**
 * usePrepStream — SSE-based prep brief hook.
 *
 * Connects to POST /sessions/{id}/prep/stream and streams the two-phase
 * rendering pipeline: extraction (blocking) → rendering (streamed token-by-token).
 *
 * Falls back to the legacy getPrepBrief endpoint on browsers that don't
 * support ReadableStream (very old Safari / IE11).
 */

import { useState, useCallback, useRef } from 'react'
import { sessionsAPI } from '@/lib/api'

export type PrepPhase = 'idle' | 'extracting' | 'rendering' | 'done' | 'error'

const MIN_VISIBLE_MS = 5000

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) || 'http://localhost:8000/api/v1'

export function usePrepStream() {
  const [phase, setPhase] = useState<PrepPhase>('idle')
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  const start = useCallback(async (sessionId: number) => {
    // Abort any in-progress request for a previous session
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    const startedAt = Date.now()

    /** Delay setPhase('done') until at least MIN_VISIBLE_MS have elapsed */
    const finishWithMinDelay = () => {
      const elapsed = Date.now() - startedAt
      const remaining = MIN_VISIBLE_MS - elapsed
      if (remaining > 0) {
        setTimeout(() => setPhase('done'), remaining)
      } else {
        setPhase('done')
      }
    }

    setPhase('extracting')
    setText('')
    setError('')

    // ── SSE streaming path (modern browsers) ──────────────────────────────
    if (typeof ReadableStream !== 'undefined') {
      try {
        const token = localStorage.getItem('access_token')
        const response = await fetch(`${BASE_URL}/sessions/${sessionId}/prep/stream`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          signal: ctrl.signal,
        })

        if (response.ok && response.body) {
          const reader = response.body.getReader()
          const decoder = new TextDecoder()
          let buf = ''

          // eslint-disable-next-line no-constant-condition
          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            buf += decoder.decode(value, { stream: true })
            const lines = buf.split('\n')
            buf = lines.pop()! // last partial line stays in buffer

            for (const line of lines) {
              if (!line.startsWith('data: ')) continue
              const data = line.slice(6)

              if (data === '[DONE]') {
                finishWithMinDelay()
                return
              }

              try {
                const parsed = JSON.parse(data)
                if (parsed.phase === 'extracting') {
                  setPhase('extracting')
                } else if (parsed.phase === 'rendering') {
                  setPhase('rendering')
                } else if (parsed.phase === 'done') {
                  finishWithMinDelay()
                  return
                } else if (parsed.chunk != null) {
                  setText((t) => t + parsed.chunk)
                } else if (parsed.error) {
                  setError(parsed.error)
                  setPhase('error')
                  return
                }
              } catch {
                // ignore malformed SSE events
              }
            }
          }

          finishWithMinDelay()
          return
        }
        // Non-OK HTTP response — fall through to legacy
      } catch (e: unknown) {
        if ((e as { name?: string }).name === 'AbortError') return
        // Network error — fall through to legacy
      }
    }

    // ── Legacy fallback: old prep-brief endpoint ───────────────────────────
    try {
      const data = await sessionsAPI.getPrepBrief(sessionId)
      const parts: string[] = []
      if (data.history_summary?.length)
        parts.push('מה היה עד עכשיו:\n' + (data.history_summary as string[]).map((s) => `• ${s}`).join('\n'))
      if (data.last_session?.length)
        parts.push('מה היה בפגישה האחרונה:\n' + (data.last_session as string[]).map((s) => `• ${s}`).join('\n'))
      if (data.tasks_to_check?.length)
        parts.push('משימות לבדיקה:\n' + (data.tasks_to_check as string[]).map((s) => `• ${s}`).join('\n'))
      if (data.focus_for_today?.length)
        parts.push('על מה כדאי להתמקד:\n' + (data.focus_for_today as string[]).map((s) => `• ${s}`).join('\n'))
      if (data.watch_out_for?.length)
        parts.push('שים לב:\n' + (data.watch_out_for as string[]).map((s) => `• ${s}`).join('\n'))
      setText(parts.join('\n\n'))
      finishWithMinDelay()
    } catch (e: unknown) {
      if ((e as { name?: string }).name === 'AbortError') return
      const axiosErr = e as { response?: { data?: { detail?: string } }; message?: string }
      setError(axiosErr.response?.data?.detail || axiosErr.message || 'שגיאה ביצירת תדריך ההכנה')
      setPhase('error')
    }
  }, [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setPhase('idle')
    setText('')
    setError('')
  }, [])

  return { phase, text, error, start, reset }
}
