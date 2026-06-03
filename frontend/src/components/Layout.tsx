/**
 * Layout — top navigation + mobile hamburger drawer + global side notebook.
 *
 * Responsive behaviour:
 *   - Desktop (sm+): horizontal nav links in top bar, user name + logout button visible
 *   - Mobile (<sm): hamburger toggles a fixed modal drawer (right side, RTL);
 *                    semi-transparent backdrop closes it on tap;
 *                    body scroll locked while drawer is open
 *   - Drawer closes automatically on route change
 *   - Lightbulb icon in header opens the SideNotebook drawer (available on all screens)
 */

import { useState, useEffect, useRef } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import { adminAPI } from '@/lib/adminApi'
import { therapistAPI } from '@/lib/api'
import {
  HomeIcon,
  ChatBubbleLeftRightIcon,
  UserGroupIcon,
  DocumentTextIcon,
  ArrowRightOnRectangleIcon,
  SparklesIcon,
  Bars3Icon,
  XMarkIcon,
  LightBulbIcon,
  QuestionMarkCircleIcon,
} from '@heroicons/react/24/outline'
import SideNotebook from '@/components/SideNotebook'
import AppLogo from '@/components/common/AppLogo'
import { strings } from '@/i18n/he'

export default function Layout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [notebookOpen, setNotebookOpen] = useState(false)

  // Feedback modal state
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [feedbackType, setFeedbackType] = useState<'bug' | 'contact'>('bug')
  const [feedbackSubject, setFeedbackSubject] = useState('')
  const [feedbackMessage, setFeedbackMessage] = useState('')
  const [feedbackSending, setFeedbackSending] = useState(false)
  const [feedbackSent, setFeedbackSent] = useState(false)
  const [feedbackError, setFeedbackError] = useState('')

  const openFeedback = (type: 'bug' | 'contact') => {
    setFeedbackType(type)
    setFeedbackSubject('')
    setFeedbackMessage('')
    setFeedbackSent(false)
    setFeedbackError('')
    setFeedbackOpen(true)
  }

  const handleFeedbackSubmit = async () => {
    if (!feedbackMessage.trim()) return
    setFeedbackSending(true)
    setFeedbackError('')
    try {
      await therapistAPI.submitFeedback(feedbackType, feedbackMessage, feedbackSubject || undefined)
      setFeedbackSent(true)
      setTimeout(() => setFeedbackOpen(false), 2000)
    } catch (err: any) {
      setFeedbackError(err?.response?.data?.detail || 'שגיאה בשליחת ההודעה. נסה שנית.')
    } finally {
      setFeedbackSending(false)
    }
  }

  // ── Easter egg: 5 rapid clicks on name/email within 3 seconds → admin panel ──
  const eggClicksRef = useRef<number[]>([])
  async function handleEggClick() {
    const now = Date.now()
    eggClicksRef.current = [...eggClicksRef.current.filter((t) => now - t < 3000), now]
    if (eggClicksRef.current.length >= 5) {
      eggClicksRef.current = []
      const password = prompt(strings.layout.admin_password_prompt)
      if (!password) return
      try {
        const token = await adminAPI.getToken(user?.email || '', password)
        sessionStorage.setItem('admin_token', token)
        navigate('/admin')
      } catch {
        alert(strings.layout.admin_access_denied)
      }
    }
  }

  // Close mobile drawer whenever the route changes
  useEffect(() => {
    setMobileMenuOpen(false)
  }, [location.pathname])

  // Lock body scroll while nav drawer is open
  // (SideNotebook manages its own scroll lock)
  useEffect(() => {
    if (!notebookOpen) {
      document.body.style.overflow = mobileMenuOpen ? 'hidden' : ''
    }
    return () => { document.body.style.overflow = '' }
  }, [mobileMenuOpen, notebookOpen])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // Show full name when available, fall back to email; hide block if neither exists
  const displayName = user?.fullName?.trim() || user?.email || null

  const getGreeting = () => {
    const h = new Date().getHours()
    if (h < 12) return strings.layout.greeting_morning
    if (h < 17) return strings.layout.greeting_afternoon
    return strings.layout.greeting_evening
  }
  const firstName = user?.fullName?.trim().split(' ')[0] || null

  const navigation = [
    { name: strings.layout.nav_home, href: '/dashboard', icon: HomeIcon },
    { name: strings.layout.nav_messages, href: '/messages', icon: ChatBubbleLeftRightIcon },
    { name: strings.layout.nav_patients, href: '/patients', icon: UserGroupIcon },
    { name: strings.layout.nav_sessions, href: '/sessions', icon: DocumentTextIcon },
    { name: strings.layout.nav_professional_settings, href: '/twin', icon: SparklesIcon },
  ]

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      {/* Top Navigation */}
      <nav className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            {/* Logo + hamburger button */}
            <div className="flex items-center gap-3">
              {/* Hamburger — visible only on mobile */}
              <button
                onClick={() => setMobileMenuOpen((v) => !v)}
                className="sm:hidden p-2 rounded-lg text-gray-500 hover:bg-gray-100 touch-manipulation min-w-[40px] min-h-[40px] flex items-center justify-center"
                aria-label={mobileMenuOpen ? strings.layout.menu_close_aria : strings.layout.menu_open_aria}
              >
                <Bars3Icon className="h-6 w-6" />
              </button>

              <div className="flex items-center gap-2">
                <AppLogo variant="icon" size="sm" />
                <span className="text-base sm:text-2xl font-bold text-therapy-calm">
                  {strings.layout.app_name}
                </span>
              </div>
            </div>

            {/* Navigation links — desktop only */}
            <div className="hidden sm:mr-6 sm:flex sm:space-x-reverse sm:space-x-8">
              {navigation.map((item) => {
                const isActive = location.pathname === item.href
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                      isActive
                        ? 'border-therapy-calm text-therapy-calm'
                        : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                    }`}
                  >
                    <item.icon className="h-5 w-5 ml-2" />
                    {item.name}
                  </Link>
                )
              })}
            </div>

            {/* User menu */}
            <div className="flex items-center gap-2 sm:gap-3">
              {/* Therapist identity — hidden on mobile */}
              {displayName && (
                // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
                <div
                  className="hidden sm:block text-sm text-gray-700 cursor-default select-none"
                  onClick={handleEggClick}
                >
                  <div className="font-medium">{displayName}</div>
                  {user?.fullName?.trim() && user?.email && (
                    <div className="text-xs text-gray-500">{user.email}</div>
                  )}
                </div>
              )}

              {/* Feedback / Help button */}
              <button
                onClick={() => openFeedback('bug')}
                className="p-2 rounded-lg touch-manipulation min-w-[40px] min-h-[40px] flex items-center justify-center text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
                title="דווח על תקלה / צור קשר"
              >
                <QuestionMarkCircleIcon className="h-5 w-5" />
              </button>

              {/* Side Notebook toggle — always visible */}
              <button
                onClick={() => setNotebookOpen((v) => !v)}
                className={`p-2 rounded-lg touch-manipulation min-w-[40px] min-h-[40px] flex items-center justify-center transition-colors ${
                  notebookOpen
                    ? 'bg-amber-100 text-amber-600'
                    : 'text-gray-500 hover:bg-gray-100'
                }`}
                aria-label={strings.layout.notes_button}
                title={strings.layout.notes_button}
              >
                <LightBulbIcon className="h-5 w-5" />
              </button>

              {/* Logout — icon-only on mobile, full label on desktop */}
              <button
                onClick={handleLogout}
                className="inline-flex items-center justify-center px-2 py-2 sm:px-4 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 min-w-[40px] min-h-[40px] touch-manipulation"
              >
                <ArrowRightOnRectangleIcon className="h-5 w-5 sm:ml-2" />
                <span className="hidden sm:inline">{strings.layout.logout_button}</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Mobile navigation drawer — fixed overlay, slides in from the right (RTL start) */}
      {mobileMenuOpen && (
        <div className="sm:hidden">
          {/* Backdrop — covers whole viewport, tap to close */}
          <div
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden="true"
          />

          {/* Drawer panel */}
          <div
            className="fixed top-0 right-0 h-full w-72 max-w-[85vw] bg-white z-50 shadow-2xl overflow-y-auto"
            dir="rtl"
          >
            <div className="px-4 py-4 space-y-1">
              {/* Drawer header — logo + greeting + close button */}
              <div className="flex items-center justify-between pb-3 mb-2 border-b border-gray-100">
                <div className="flex items-center gap-2">
                  <AppLogo variant="icon" size="md" />
                  <div>
                    <div className="text-xs font-bold text-therapy-calm">{strings.layout.app_name}</div>
                    <div className="text-sm font-medium text-gray-700">
                      {firstName ? `${getGreeting()}, ${firstName}` : getGreeting()}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 touch-manipulation min-w-[40px] min-h-[40px] flex items-center justify-center"
                  aria-label={strings.layout.menu_close_aria}
                >
                  <XMarkIcon className="h-6 w-6" />
                </button>
              </div>

              {navigation.map((item) => {
                const isActive = location.pathname === item.href
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={`flex items-center gap-3 px-3 py-3 rounded-lg text-base font-medium min-h-[44px] touch-manipulation ${
                      isActive
                        ? 'bg-therapy-calm/10 text-therapy-calm'
                        : 'text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    <item.icon className="h-6 w-6 flex-shrink-0" />
                    {item.name}
                  </Link>
                )
              })}

              {/* Therapist identity + logout inside drawer */}
              <div className="pt-3 mt-2 border-t border-gray-100">
                {displayName && (
                  <div className="text-sm text-gray-700 px-3 mb-2">
                    <div className="font-medium">{displayName}</div>
                    {user?.fullName?.trim() && user?.email && (
                      <div className="text-xs text-gray-500">{user.email}</div>
                    )}
                  </div>
                )}
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-3 px-3 py-3 rounded-lg text-base font-medium text-red-600 hover:bg-red-50 w-full min-h-[44px] touch-manipulation"
                >
                  <ArrowRightOnRectangleIcon className="h-6 w-6" />
                  {strings.layout.logout_button}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Global Side Notebook drawer */}
      <SideNotebook open={notebookOpen} onClose={() => setNotebookOpen(false)} />

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5 sm:py-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 text-sm text-gray-500">
            {/* Full logo on sm+, icon-only on xs */}
            <AppLogo variant="full" size="sm" className="hidden sm:block" />
            <AppLogo variant="icon" size="sm" className="sm:hidden" />
            <div className="text-center sm:text-right">
              <p className="font-medium text-gray-600">{strings.layout.footer_subtitle}</p>
              <p className="mt-0.5 text-xs">{strings.layout.footer_security}</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <button onClick={() => openFeedback('bug')} className="text-gray-400 hover:text-gray-600 underline">דווח על תקלה</button>
              <span>·</span>
              <button onClick={() => openFeedback('contact')} className="text-gray-400 hover:text-gray-600 underline">צור קשר</button>
            </div>
          </div>
        </div>
      </footer>

      {/* Feedback modal */}
      {feedbackOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" dir="rtl">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <div>
                <h2 className="text-lg font-bold text-gray-900">
                  {feedbackType === 'bug' ? 'דווח על תקלה' : 'צור קשר'}
                </h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  {feedbackType === 'bug' ? 'דיווחך יגיע ישירות לצוות הפיתוח' : 'נחזור אליך בהקדם לכתובת: info@metapel.online'}
                </p>
              </div>
              <button onClick={() => setFeedbackOpen(false)} className="text-gray-400 hover:text-gray-600 p-1">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>

            <div className="px-5 py-4 space-y-3">
              {/* Type tabs */}
              <div className="flex gap-2">
                {(['bug', 'contact'] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setFeedbackType(t)}
                    className={`flex-1 py-1.5 text-sm rounded-lg font-medium transition-colors ${
                      feedbackType === t ? 'bg-therapy-calm text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {t === 'bug' ? 'דווח על תקלה' : 'יצירת קשר'}
                  </button>
                ))}
              </div>

              <input
                type="text"
                value={feedbackSubject}
                onChange={(e) => setFeedbackSubject(e.target.value)}
                placeholder={feedbackType === 'bug' ? 'כותרת התקלה (אופציונלי)' : 'נושא (אופציונלי)'}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
              />

              <textarea
                value={feedbackMessage}
                onChange={(e) => setFeedbackMessage(e.target.value)}
                placeholder={feedbackType === 'bug' ? 'תאר את התקלה — מה קרה, מתי, באיזה מסך...' : 'כתוב את הודעתך כאן...'}
                rows={5}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
              />

              {feedbackError && (
                <div className="text-red-600 text-sm bg-red-50 rounded-lg p-2">{feedbackError}</div>
              )}
              {feedbackSent && (
                <div className="text-green-700 text-sm bg-green-50 rounded-lg p-2 font-medium">ההודעה נשלחה בהצלחה ✓</div>
              )}
            </div>

            <div className="flex gap-3 px-5 py-4 border-t border-gray-100">
              <button
                onClick={handleFeedbackSubmit}
                disabled={!feedbackMessage.trim() || feedbackSending || feedbackSent}
                className="btn-primary flex-1 disabled:opacity-50"
              >
                {feedbackSending ? 'שולח...' : 'שלח'}
              </button>
              <button onClick={() => setFeedbackOpen(false)} className="btn-secondary flex-1">
                ביטול
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
