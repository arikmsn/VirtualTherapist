import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import OnboardingPage from './pages/OnboardingPage'
import MessagesPage from './pages/MessagesPage'
import PatientsPage from './pages/PatientsPage'
import SessionsPage from './pages/SessionsPage'
import SessionDetailPage from './pages/SessionDetailPage'
import Layout from './components/Layout'

function App() {
  const { isAuthenticated } = useAuthStore()

  return (
    <Router>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={!isAuthenticated ? <LoginPage /> : <Navigate to="/dashboard" />} />
        <Route path="/register" element={!isAuthenticated ? <RegisterPage /> : <Navigate to="/dashboard" />} />

        {/* Protected routes */}
        <Route element={isAuthenticated ? <Layout /> : <Navigate to="/login" />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/messages" element={<MessagesPage />} />
          <Route path="/patients" element={<PatientsPage />} />
          <Route path="/sessions" element={<SessionsPage />} />
          <Route path="/sessions/:sessionId" element={<SessionDetailPage />} />
        </Route>

        {/* Default redirect */}
        <Route path="/" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} />} />
      </Routes>
    </Router>
  )
}

export default App
