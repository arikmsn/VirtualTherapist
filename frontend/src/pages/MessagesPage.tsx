import { useState, useEffect } from 'react'
import { messagesAPI } from '@/lib/api'
import {
  CheckCircleIcon,
  XCircleIcon,
  PencilIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'

interface Message {
  id: number
  patient_id: number
  content: string
  status: string
  message_type: string
  created_at: string
  requires_approval: boolean
}

export default function MessagesPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editContent, setEditContent] = useState('')

  useEffect(() => {
    loadMessages()
  }, [])

  const loadMessages = async () => {
    try {
      const data = await messagesAPI.getPending()
      setMessages(data)
    } catch (error) {
      console.error('Error loading messages:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (id: number) => {
    try {
      await messagesAPI.approve(id)
      setMessages(messages.filter((m) => m.id !== id))
    } catch (error) {
      console.error('Error approving message:', error)
    }
  }

  const handleReject = async (id: number) => {
    try {
      await messagesAPI.reject(id, 'דחוי על ידי המטפל')
      setMessages(messages.filter((m) => m.id !== id))
    } catch (error) {
      console.error('Error rejecting message:', error)
    }
  }

  const handleEdit = (message: Message) => {
    setEditingId(message.id)
    setEditContent(message.content)
  }

  const handleSaveEdit = async (id: number) => {
    try {
      await messagesAPI.edit(id, editContent)
      setMessages(
        messages.map((m) =>
          m.id === id ? { ...m, content: editContent } : m
        )
      )
      setEditingId(null)
    } catch (error) {
      console.error('Error editing message:', error)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">הודעות ממתינות לאישור</h1>
          <p className="text-gray-600 mt-2">
            בדוק ואשר הודעות לפני שליחתן למטופלים
          </p>
        </div>
        {messages.length > 0 && (
          <div className="badge badge-pending text-lg px-4 py-2">
            {messages.length} הודעות ממתינות
          </div>
        )}
      </div>

      {/* Messages List */}
      {messages.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-6xl mb-4">✅</div>
          <h3 className="text-xl font-bold text-gray-900 mb-2">
            אין הודעות ממתינות
          </h3>
          <p className="text-gray-600">
            כל ההודעות אושרו ונשלחו! עבודה מצוינת 🎉
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {messages.map((message) => (
            <div key={message.id} className="card hover:shadow-xl transition-shadow">
              {/* Message Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-therapy-calm text-white rounded-full flex items-center justify-center font-bold">
                    מ
                  </div>
                  <div>
                    <div className="font-medium">מטופל #{message.patient_id}</div>
                    <div className="text-sm text-gray-500">
                      סוג: {getMessageTypeLabel(message.message_type)}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <ClockIcon className="h-4 w-4" />
                  {new Date(message.created_at).toLocaleString('he-IL')}
                </div>
              </div>

              {/* Message Content */}
              <div className="bg-gray-50 rounded-lg p-4 mb-4">
                {editingId === message.id ? (
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    className="input-field h-32 resize-none"
                  />
                ) : (
                  <p className="text-gray-800 whitespace-pre-wrap leading-relaxed">
                    {message.content}
                  </p>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-3">
                {editingId === message.id ? (
                  <>
                    <button
                      onClick={() => handleSaveEdit(message.id)}
                      className="flex-1 btn-success flex items-center justify-center gap-2"
                    >
                      <CheckCircleIcon className="h-5 w-5" />
                      שמור שינויים
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="flex-1 btn-secondary"
                    >
                      ביטול
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => handleApprove(message.id)}
                      className="flex-1 btn-success flex items-center justify-center gap-2"
                    >
                      <CheckCircleIcon className="h-5 w-5" />
                      אשר ושלח
                    </button>
                    <button
                      onClick={() => handleEdit(message)}
                      className="flex-1 btn-secondary flex items-center justify-center gap-2"
                    >
                      <PencilIcon className="h-5 w-5" />
                      ערוך
                    </button>
                    <button
                      onClick={() => handleReject(message.id)}
                      className="flex-1 bg-red-100 text-red-700 px-6 py-4 rounded-lg font-medium hover:bg-red-200 transition-all flex items-center justify-center gap-2"
                    >
                      <XCircleIcon className="h-5 w-5" />
                      דחה
                    </button>
                  </>
                )}
              </div>

              {/* Warning */}
              {message.requires_approval && (
                <div className="mt-4 bg-amber-50 border border-amber-200 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-amber-800 text-sm">
                    <span>⚠️</span>
                    <span className="font-medium">
                      הודעה זו תישלח למטופל רק לאחר אישורך המפורש
                    </span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function getMessageTypeLabel(type: string): string {
  const labels: { [key: string]: string } = {
    follow_up: 'מעקב',
    exercise_reminder: 'תזכורת לתרגיל',
    check_in: 'צ\'ק-אין',
    session_reminder: 'תזכורת לפגישה',
  }
  return labels[type] || type
}
