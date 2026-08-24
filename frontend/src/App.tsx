import { lazy, Suspense } from "react";
import { Routes, Route, Navigate, useLocation, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CircularProgress, Box } from "@mui/material";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import AppLayout from "./pages/AppLayout";
import { projectsApi } from "./api/resources";

// Code-splitting: las páginas pesadas se cargan bajo demanda
const LoginPage = lazy(() => import("./pages/LoginPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const TasksPage = lazy(() => import("./pages/TasksPage"));
const TagsPage = lazy(() => import("./pages/TagsPage"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));
const IntegrationsPage = lazy(() => import("./pages/IntegrationsPage"));
const GitHubCallbackPage = lazy(() => import("./pages/GitHubCallbackPage"));
const SprintsPage = lazy(() => import("./pages/SprintsPage"));
const EpicsPage = lazy(() => import("./pages/EpicsPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const AutomationsPage = lazy(() => import("./pages/AutomationsPage"));
const AuditPage = lazy(() => import("./pages/AuditPage"));
const ApiKeysPage = lazy(() => import("./pages/ApiKeysPage"));
const SecurityPage = lazy(() => import("./pages/SecurityPage"));
const GanttPage = lazy(() => import("./pages/GanttPage"));
const BurndownPage = lazy(() => import("./pages/BurndownPage"));
const CapacityPage = lazy(() => import("./pages/CapacityPage"));
const OkrsPage = lazy(() => import("./pages/OkrsPage"));
const AiAssistantPage = lazy(() => import("./pages/AiAssistantPage"));

function Loading() {
  return (
    <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
      <CircularProgress />
    </Box>
  );
}

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading)
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  if (!user)
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <>{children}</>;
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/app" replace />;
  return <>{children}</>;
}

function ProjectTasks() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const { data: project } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
    select: (list: unknown) =>
      Array.isArray(list) ? list.find((p) => p.id === id) : undefined,
  });
  return <TasksPage projectId={id} title={project?.name || "Proyecto"} />;
}

export default function App() {
  return (
    <AuthProvider>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
          <Route path="/register" element={<PublicOnly><RegisterPage /></PublicOnly>} />
          <Route path="/auth/github/callback" element={<GitHubCallbackPage />} />
          <Route
            path="/app"
            element={
              <Protected>
                <AppLayout />
              </Protected>
            }
          >
            <Route index element={<TasksPage title="Bandeja de entrada" />} />
            <Route path="project/:projectId" element={<ProjectTasks />} />
            <Route path="tags" element={<TagsPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="integrations" element={<IntegrationsPage />} />
            <Route path="sprints" element={<SprintsPage />} />
            <Route path="epics" element={<EpicsPage />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="automations" element={<AutomationsPage />} />
            <Route path="audit" element={<AuditPage />} />
            <Route path="api-keys" element={<ApiKeysPage />} />
            <Route path="security" element={<SecurityPage />} />
            <Route path="gantt" element={<GanttPage />} />
            <Route path="burndown" element={<BurndownPage />} />
            <Route path="capacity" element={<CapacityPage />} />
            <Route path="okrs" element={<OkrsPage />} />
            <Route path="ai-assistant" element={<AiAssistantPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/app" replace />} />
        </Routes>
      </Suspense>
    </AuthProvider>
  );
}
