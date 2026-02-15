import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import {
  HomeIcon,
  ChatBubbleLeftRightIcon,
  UserGroupIcon,
  DocumentTextIcon,
  ArrowRightOnRectangleIcon,
} from '@heroicons/react/24/outline'

export default function Layout() {
  const { user, logout } = useAuthStore()
  const location = useLocation()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navigation = [
    { name: 'ראשי', href: '/dashboard', icon: HomeIcon },
    { name: 'הודעות', href: '/messages', icon: ChatBubbleLeftRightIcon },
    { name: 'מטופלים', href: '/patients', icon: UserGroupIcon },
    { name: 'פגישות', href: '/sessions', icon: DocumentTextIcon },
  ]

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      {/* Top Navigation */}
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            {/* Logo and brand */}
            <div className="flex items-center">
              <div className="flex-shrink-0 flex items-center">
                <div className="text-2xl font-bold text-therapy-calm">
                  🧠 TherapyCompanion.AI
                </div>
              </div>
            </div>

            {/* Navigation links */}
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
            <div className="flex items-center gap-4">
              <div className="text-sm text-gray-700">
                <div className="font-medium">{user?.fullName}</div>
                <div className="text-xs text-gray-500">{user?.email}</div>
              </div>
              <button
                onClick={handleLogout}
                className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                <ArrowRightOnRectangleIcon className="h-5 w-5 ml-2" />
                התנתק
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
