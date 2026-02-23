/**
 * Layout — top navigation + mobile hamburger drawer.
 *
 * Responsive behaviour:
 *   - Desktop (sm+): horizontal nav links in top bar, user name + logout button visible
 *   - Mobile (<sm): hamburger toggles a fixed modal drawer (right side, RTL);
 *                    semi-transparent backdrop closes it on tap;
 *                    body scroll locked while drawer is open
 *   - Drawer closes automatically on route change
 */

import { useState, useEffect } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import {
  HomeIcon,
  ChatBubbleLeftRightIcon,
  UserGroupIcon,
  DocumentTextIcon,
  ArrowRightOnRectangleIcon,
  SparklesIcon,
  Bars3Icon,
  XMarkIcon,
} from '@heroicons/react/24/outline'

export default function Layout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  // Close mobile drawer whenever the route changes
  useEffect(() => {
    setMobileMenuOpen(false)
  }, [location.pathname])

  // Lock body scroll while drawer is open
  useEffect(() => {
    document.body.style.overflow = mobileMenuOpen ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [mobileMenuOpen])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // Show full name when available, fall back to email; hide block if neither exists
  const displayName = user?.fullName?.trim() || user?.email || null

  const navigation = [
    { name: 'ראשי', href: '/dashboard', icon: HomeIcon },
    { name: 'הודעות', href: '/messages', icon: ChatBubbleLeftRightIcon },
    { name: 'מטופלים', href: '/patients', icon: UserGroupIcon },
    { name: 'פגישות', href: '/sessions', icon: DocumentTextIcon },
    { name: 'פרופיל AI', href: '/twin', icon: SparklesIcon },
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
                aria-label={mobileMenuOpen ? 'סגור תפריט' : 'פתח תפריט'}
              >
                <Bars3Icon className="h-6 w-6" />
              </button>

              <div className="text-lg sm:text-2xl font-bold text-therapy-calm">
                🧠 <span className="hidden xs:inline">TherapyCompanion.AI</span>
                <span className="xs:hidden sm:hidden">TC.AI</span>
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
            <div className="flex items-center gap-2 sm:gap-4">
              {/* Therapist identity — hidden on mobile */}
              {displayName && (
                <div className="hidden sm:block text-sm text-gray-700">
                  <div className="font-medium">{displayName}</div>
                  {user?.fullName?.trim() && user?.email && (
                    <div className="text-xs text-gray-500">{user.email}</div>
                  )}
                </div>
              )}

              {/* Logout — icon-only on mobile, full label on desktop */}
              <button
                onClick={handleLogout}
                className="inline-flex items-center justify-center px-2 py-2 sm:px-4 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 min-w-[40px] min-h-[40px] touch-manipulation"
              >
                <ArrowRightOnRectangleIcon className="h-5 w-5 sm:ml-2" />
                <span className="hidden sm:inline">התנתק</span>
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
              {/* Drawer header — app name + close button */}
              <div className="flex items-center justify-between pb-3 mb-2 border-b border-gray-100">
                <div className="text-lg font-bold text-therapy-calm">🧠 TC.AI</div>
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 touch-manipulation min-w-[40px] min-h-[40px] flex items-center justify-center"
                  aria-label="סגור תפריט"
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
                  התנתק
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5 sm:py-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="text-center text-sm text-gray-500">
            <p>TherapyCompanion.AI - עוזר טיפולי חכם למטפלים</p>
            <p className="mt-1 text-xs">מוצפן מקצה לקצה | תואם GDPR | נתונים בישראל/אירופה בלבד</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
