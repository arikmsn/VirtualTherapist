import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import AuthProvider from './auth/AuthProvider'
import { useAuth } from './auth/useAuth'
import ProtectedRoute from './auth/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import OnboardingPage from './pages/OnboardingPage'
import MessagesPage from './pages/MessagesPage'
import PatientsPage from './pages/PatientsPage'
import SessionsPage from './pages/SessionsPage'
import SessionDetailPage from './pages/SessionDetailPage'
import PatientSummariesPage from './pages/PatientSummariesPage'
import PatientProfilePage from './pages/PatientProfilePage'
import TwinProfilePage from './pages/TwinProfilePage'
import GoogleCallbackPage from './pages/GoogleCallbackPage'
import PrintSessionPage from './pages/PrintSessionPage'
import PrintPatientPage from './pages/PrintPatientPage'
import Layout from './components/Layout'
import AdminGuard from './pages/admin/AdminGuard'
import AdminLayout from './pages/admin/AdminLayout'
import AdminDashboardPage from './pages/admin/AdminDashboardPage'
import AdminTherapistsPage from './pages/admin/AdminTherapistsPage'
import AdminUsagePage from './pages/admin/AdminUsagePage'
import AdminAlertsPage from './pages/admin/AdminAlertsPage'

function AppRoutes() {
  const { isAuthenticated, isReady, onboardingCompleted } = useAuth()

  // Wait for auth to initialize from localStorage before rendering routes.
  // Without this, the initial isAuthenticated=false triggers a redirect
  // to /login before the stored token is read, causing a flash.
  if (!isReady) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
      </div>
    )
  }

  // Onboarding gate: if authenticated but profile not yet loaded, show spinner.
  // Once loaded, if not completed redirect to /onboarding (handled inside ProtectedRoute).
  const onboardingLoading = isAuthenticated && onboardingCompleted === null

  if (onboardingLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
      </div>
    )
  }

  // If authenticated but onboarding not done, force /onboarding (full-screen, no Layout)
  const needsOnboarding = isAuthenticated && onboardingCompleted === false

  return (
    <Router>
      <Routes>
        {/* Public routes — redirect to dashboard if already logged in */}
        <Route path="/login" element={!isAuthenticated ? <LoginPage /> : <Navigate to="/dashboard" />} />
        <Route path="/register" element={!isAuthenticated ? <RegisterPage /> : <Navigate to="/dashboard" />} />
        {/* Google OAuth callback — always public, handles its own auth state */}
        <Route path="/auth/google/callback" element={<GoogleCallbackPage />} />

        {/* Onboarding — full-screen, no sidebar/nav, inside ProtectedRoute but outside Layout */}
        <Route element={<ProtectedRoute />}>
          <Route path="/onboarding" element={<OnboardingPage />} />
        </Route>

        {/* Print views — full-screen, no sidebar/nav */}
        <Route element={<ProtectedRoute />}>
          <Route path="/sessions/:sessionId/print" element={<PrintSessionPage />} />
          <Route path="/patients/:patientId/print" element={<PrintPatientPage />} />
        </Route>

        {/* Protected routes — redirect to /onboarding if not completed */}
        <Route element={<ProtectedRoute />}>
          <Route element={needsOnboarding ? <Navigate to="/onboarding" replace /> : <Layout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/messages" element={<MessagesPage />} />
            <Route path="/patients" element={<PatientsPage />} />
            <Route path="/patients/:patientId" element={<PatientProfilePage />} />
            <Route path="/patients/:patientId/summaries" element={<PatientSummariesPage />} />
            <Route path="/twin" element={<TwinProfilePage />} />
            <Route path="/sessions" element={<SessionsPage />} />
            <Route path="/sessions/:sessionId" element={<SessionDetailPage />} />
          </Route>
        </Route>

        {/* Admin panel — guarded by sessionStorage admin_token */}
        <Route element={<AdminGuard />}>
          <Route element={<AdminLayout />}>
            <Route path="/admin" element={<AdminDashboardPage />} />
            <Route path="/admin/therapists" element={<AdminTherapistsPage />} />
            <Route path="/admin/usage" element={<AdminUsagePage />} />
            <Route path="/admin/alerts" element={<AdminAlertsPage />} />
          </Route>
        </Route>

        {/* Default redirect */}
        <Route path="/" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} />} />
      </Routes>
    </Router>
  )
}

function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}

export default App
