/**
 * AdminLayout — sidebar + content shell for all admin pages.
 * Fully separate from the main app layout (no main nav, no patient context).
 */

import { NavLink, Outlet, useNavigate } from 'react-router-dom'

const NAV = [
  { to: '/admin', label: 'לוח בקרה', icon: '📊', end: true },
  { to: '/admin/therapists', label: 'מטפלים', icon: '👥' },
  { to: '/admin/usage', label: 'שימוש AI', icon: '🤖' },
  { to: '/admin/alerts', label: 'התראות', icon: '🔔' },
]

export default function AdminLayout() {
  const navigate = useNavigate()

  function logout() {
    sessionStorage.removeItem('admin_token')
    navigate('/')
  }

  return (
    <div className="min-h-screen flex bg-gray-950 text-white" dir="rtl">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 flex flex-col bg-gray-900 border-l border-gray-800">
        {/* Logo area */}
        <div className="px-5 py-6 border-b border-gray-800">
          <p className="text-xs font-semibold text-indigo-400 uppercase tracking-widest mb-0.5">
            Admin Panel
          </p>
          <p className="text-sm text-gray-300 font-medium">metapel.online</p>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 space-y-0.5 px-2">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-indigo-600 text-white font-medium'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`
              }
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-gray-800">
          <button
            onClick={logout}
            className="w-full text-right px-3 py-2 text-xs text-gray-500 hover:text-red-400 transition-colors rounded-lg hover:bg-gray-800"
          >
            יציאה מהפאנל ←
          </button>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
