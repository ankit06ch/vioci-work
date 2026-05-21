import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './styles.css'
import './auth.css'
import { AppShell } from './components/AppShell'
import { ProtectedRoute } from './components/ProtectedRoute'
import { Docs } from './pages/Docs'
import { EnterpriseSignup } from './pages/EnterpriseSignup'
import { Home } from './pages/Home'
import { Login } from './pages/Login'
import { FileExplorer } from './pages/FileExplorer'
import { ProjectView } from './pages/ProjectView'
import { Signup } from './pages/Signup'

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/signup/enterprise" element={<EnterpriseSignup />} />
      <Route
        path="/workspace"
        element={
          <ProtectedRoute>
            <FileExplorer />
          </ProtectedRoute>
        }
      />
      <Route path="/upload" element={<Navigate to="/workspace" replace />} />
      <Route
        path="/docs"
        element={
          <ProtectedRoute>
            <Docs />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId"
        element={
          <ProtectedRoute>
            <ProjectView />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <AppRoutes />
      </AppShell>
    </BrowserRouter>
  )
}
