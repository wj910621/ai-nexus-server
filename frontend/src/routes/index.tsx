import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Spin } from 'antd'
import ProtectedRoute from '@/components/common/ProtectedRoute'
import MainLayout from '@/components/layout/MainLayout'

const LoginPage = lazy(() => import('@/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const ProjectListPage = lazy(() => import('@/pages/ProjectListPage'))
const ProjectEditorPage = lazy(() => import('@/pages/ProjectEditorPage'))
const FirstLaunchPage = lazy(() => import('@/pages/FirstLaunchPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const TrainingPage = lazy(() => import('@/pages/TrainingPage'))
const BillingPage = lazy(() => import('@/pages/BillingPage'))
const TermsPage = lazy(() => import('@/pages/TermsPage'))
const AgentPage = lazy(() => import('@/pages/AgentPage'))
const TemplatesPage = lazy(() => import('@/pages/TemplatesPage'))
const WorkflowPage = lazy(() => import('@/pages/WorkflowPage'))

const Loading = () => (
  <div className="flex items-center justify-center h-screen">
    <Spin size="large" />
  </div>
)

export default function AppRoutes() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/first-launch" element={<FirstLaunchPage />} />
        <Route path="/terms" element={<TermsPage />} />

        <Route
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/agent" element={<AgentPage />} />
          <Route path="/templates" element={<TemplatesPage />} />
          <Route path="/workflow" element={<WorkflowPage />} />
          <Route path="/projects" element={<ProjectListPage />} />
          <Route path="/projects/:projectId" element={<ProjectEditorPage />} />
          <Route path="/characters/:id/train" element={<TrainingPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/billing" element={<BillingPage />} />
        </Route>

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Suspense>
  )
}
