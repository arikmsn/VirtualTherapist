/**
 * SideNotebook — global therapist idea vault.
 *
 * A fixed right-side drawer (RTL: right = start) that stores personal notes
 * not tied to any patient. Accessible from the app header via a lightbulb icon.
 *
 * Features:
 *  - Create / edit / delete notes (title optional, content required)
 *  - Optional comma-separated tags
 *  - AI assist on current editor text
 *  - Notes list in reverse-chronological order; click to load into editor
 */

import { useState, useEffect } from 'react'
import {
  XMarkIcon,
  TrashIcon,
  TagIcon,
} from '@heroicons/react/24/outline'
import { therapistNotesAPI } from '@/lib/api'

interface SideNote {
  id: number
  title?: string | null
  content: string
  tags?: string[] | null
  created_at: string
  updated_at: string
}

interface Props {
  open: boolean
  onClose: () => void
}

export default function SideNotebook({ open, onClose }: Props) {
  const [notes, setNotes] = useState<SideNote[]>([])
  const [notesLoading, setNotesLoading] = useState(false)

  // Editor state
  const [editingId, setEditingId] = useState<number | null>(null)  // null = new note
  const [editorTitle, setEditorTitle] = useState('')
  const [editorContent, setEditorContent] = useState('')
  const [editorTags, setEditorTags] = useState('')   // comma-separated input

  const [saving, setSaving] = useState(false)

  // Load notes when drawer opens
  useEffect(() => {
    if (!open) return
    const load = async () => {
      setNotesLoading(true)
      try {
        const data = await therapistNotesAPI.list()
        setNotes(data)
      } catch { /* not critical */ } finally {
        setNotesLoading(false)
      }
    }
    load()
  }, [open])

  // Body scroll lock while open
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  const resetEditor = () => {
    setEditingId(null)
    setEditorTitle('')
    setEditorContent('')
    setEditorTags('')
  }

  const loadNoteIntoEditor = (note: SideNote) => {
    setEditingId(note.id)
    setEditorTitle(note.title || '')
    setEditorContent(note.content)
    setEditorTags((note.tags || []).join(', '))
  }

  const handleSave = async () => {
    if (!editorContent.trim()) return
    setSaving(true)
    const tags = editorTags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)

    try {
      if (editingId !== null) {
        const updated = await therapistNotesAPI.update(editingId, {
          title: editorTitle.trim() || undefined,
          content: editorContent,
          tags: tags.length ? tags : undefined,
        })
        setNotes((prev) => prev.map((n) => (n.id === editingId ? updated : n)))
      } else {
        const created = await therapistNotesAPI.create({
          title: editorTitle.trim() || undefined,
          content: editorContent,
          tags: tags.length ? tags : undefined,
        })
        setNotes((prev) => [created, ...prev])
      }
      resetEditor()
    } catch { /* swallow — not critical */ } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (noteId: number) => {
    try {
      await therapistNotesAPI.delete(noteId)
      setNotes((prev) => prev.filter((n) => n.id !== noteId))
      if (editingId === noteId) resetEditor()
    } catch { /* swallow */ }
  }

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString('he-IL', { day: 'numeric', month: 'short', year: 'numeric' })

  return (
    <div dir="rtl">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer panel — right side (RTL start), full height */}
      <div className="fixed top-0 right-0 h-full w-full sm:w-96 bg-white z-50 shadow-2xl flex flex-col overflow-hidden">

        {/* Header */}
        <div className="flex items-start justify-between px-4 py-4 border-b border-gray-100 flex-shrink-0">
          <div>
            <h2 className="text-lg font-bold text-gray-900">מחברת צד</h2>
            <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">
              מקום לשמור רעיונות, תובנות ולינקים שאינם קשורים למטופל ספציפי.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-gray-400 hover:bg-gray-100 touch-manipulation flex-shrink-0"
            aria-label="סגור"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto">

          {/* Editor area */}
          <div className="px-4 py-4 border-b border-gray-100 space-y-3">
            <input
              type="text"
              value={editorTitle}
              onChange={(e) => setEditorTitle(e.target.value)}
              placeholder="כותרת (אופציונלי)"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
            />
            <textarea
              value={editorContent}
              onChange={(e) => setEditorContent(e.target.value)}
              placeholder="רשום רעיון, תובנה, לינק..."
              rows={4}
              maxLength={1000}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm resize-none"
            />
            <p className="text-right text-xs text-gray-400 -mt-1">{editorContent.length}/1000</p>

            {/* Tags input */}
            <div className="flex items-center gap-2">
              <TagIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
              <input
                type="text"
                value={editorTags}
                onChange={(e) => setEditorTags(e.target.value)}
                placeholder="תגיות: CBT, חרדה, מאמר (מופרדות בפסיק)"
                className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-xs focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
              />
            </div>

            {/* Action buttons */}
            <div className="flex gap-2 justify-end">
              {editingId !== null && (
                <button
                  onClick={resetEditor}
                  className="btn-secondary text-sm"
                >
                  חדש
                </button>
              )}
              <button
                onClick={handleSave}
                disabled={!editorContent.trim() || saving}
                className="btn-primary text-sm disabled:opacity-50"
              >
                {saving ? 'שומר...' : editingId !== null ? 'עדכן' : 'שמור'}
              </button>
            </div>
          </div>

          {/* Notes list */}
          <div className="px-4 py-3">
            {notesLoading ? (
              <div className="flex justify-center py-6">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-therapy-calm" />
              </div>
            ) : notes.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">
                אין פתקים עדיין. רשום את הרעיון הראשון שלך!
              </p>
            ) : (
              <div className="space-y-2">
                <h3 className="text-xs font-medium text-gray-400 mb-2">פתקים שמורים ({notes.length})</h3>
                {notes.map((note) => (
                  <div
                    key={note.id}
                    className={`rounded-xl border px-3 py-2.5 cursor-pointer transition-colors ${
                      editingId === note.id
                        ? 'border-therapy-calm bg-therapy-calm/5'
                        : 'border-gray-200 bg-gray-50 hover:bg-white hover:border-gray-300'
                    }`}
                    onClick={() => loadNoteIntoEditor(note)}
                  >
                    <div className="flex items-start gap-2">
                      <div className="flex-1 min-w-0">
                        {note.title && (
                          <p className="text-sm font-semibold text-gray-800 truncate">{note.title}</p>
                        )}
                        <p className="text-xs text-gray-600 line-clamp-2 mt-0.5">{note.content}</p>
                        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                          <span className="text-[10px] text-gray-400">{formatDate(note.created_at)}</span>
                          {(note.tags || []).map((tag) => (
                            <span
                              key={tag}
                              className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded-full"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(note.id) }}
                        className="flex-shrink-0 text-gray-300 hover:text-red-400 transition-colors p-1 touch-manipulation"
                        title="מחק פתק"
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
