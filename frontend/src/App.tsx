import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { LoginPage } from './components/auth/LoginPage';
import { DashboardView } from './components/dashboard/DashboardView';
import { GisExplorerView } from './components/map/GisExplorerView';
import { AnalysisWorkspace } from './components/analysis/AnalysisWorkspace';
import { BenchmarkView } from './components/benchmarks/BenchmarkView';
import { ReportsView } from './components/reports/ReportsView';
import { SettingsView } from './components/settings/SettingsView';
import { UsersView } from './components/users/UsersView';
import { JobsView } from './components/jobs/JobsView';
import { DetectionReviewView } from './components/review/DetectionReviewView';
import { UploadProvider } from './context/UploadContext';
import { AppShell } from './routing/AppShell';
import { ProtectedRoute } from './routing/ProtectedRoute';
import { RoleRoute } from './routing/RoleRoute';
import { NotFound } from './routing/NotFound';

/** /login: redirect to dashboard when already authenticated, else show the login page. */
function LoginRoute() {
  const { user, loading } = useAuth();
  if (loading) return null;
  return user ? <Navigate to="/dashboard" replace /> : <LoginPage />;
}

function AppContent() {
  const navigate = useNavigate();
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />

      {/* Everything below requires authentication (ProtectedRoute) and renders inside AppShell */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardView onNavigateMap={() => navigate('/map')} onNavigateAnalysis={() => navigate('/upload')} />} />
          <Route path="/map" element={<GisExplorerView onNavigateUpload={() => navigate('/upload')} />} />
          <Route path="/upload" element={<AnalysisWorkspace onNavigateMap={() => navigate('/map')} />} />
          <Route path="/jobs" element={<JobsView />} />
          <Route path="/analyses/:analysisId/review" element={<DetectionReviewView />} />
          <Route path="/benchmarks" element={<BenchmarkView />} />
          <Route path="/reports" element={<ReportsView />} />
          <Route path="/admin/users" element={<RoleRoute roles={['admin']}><UsersView /></RoleRoute>} />
          <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
          <Route path="/settings" element={<SettingsView />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <UploadProvider>
          <Router>
            <AppContent />
          </Router>
        </UploadProvider>
      </AuthProvider>
    </ToastProvider>
  );
}
