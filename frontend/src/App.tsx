import { lazy, Suspense } from "react";
import { Routes, Route, Navigate, useLocation, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CircularProgress, Box } from "@mui/material";
import { PageSkeleton } from "./components/ui/skeletons";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { ProjectProvider } from "./auth/ProjectContext";
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
const RoadmapPage = lazy(() => import("./pages/RoadmapPage"));
const MyWorkPage = lazy(() => import("./pages/MyWorkPage"));
const WikiPage = lazy(() => import("./pages/WikiPage"));
const AiAssistantPage = lazy(() => import("./pages/AiAssistantPage"));
const ProjectsPage = lazy(() => import("./pages/ProjectsPage"));
const GitHubPage = lazy(() => import("./pages/GitHubPage"));
const NotificationsPage = lazy(() => import("./pages/NotificationsPage"));
const TimeEntriesPage = lazy(() => import("./pages/TimeEntriesPage"));
const TaskTemplatesPage = lazy(() => import("./pages/TaskTemplatesPage"));
const CustomFieldsPage = lazy(() => import("./pages/CustomFieldsPage"));
const WebhooksPage = lazy(() => import("./pages/WebhooksPage"));
const FeatureFlagsPage = lazy(() => import("./pages/FeatureFlagsPage"));
const TeamsPage = lazy(() => import("./pages/TeamsPage"));
const OfflineSyncPage = lazy(() => import("./pages/OfflineSyncPage"));
const EncryptionPage = lazy(() => import("./pages/EncryptionPage"));
const RecurrenceRulesPage = lazy(() => import("./pages/RecurrenceRulesPage"));
const HomePage = lazy(() => import("./pages/HomePage"));
const ProjectOverviewPage = lazy(() => import("./pages/ProjectOverviewPage"));
const BacklogPage = lazy(() => import("./pages/BacklogPage"));
const WorkflowEditorPage = lazy(() => import("./pages/WorkflowEditorPage"));
const AdminPage = lazy(() => import("./pages/AdminPage"));
const RolesPage = lazy(() => import("./pages/RolesPage"));
const TrashPage = lazy(() => import("./pages/TrashPage"));
const MeetingsPage = lazy(() => import("./pages/MeetingsPage"));
const RisksPage = lazy(() => import("./pages/RisksPage"));
const IntakeFormsPage = lazy(() => import("./pages/IntakeFormsPage"));
const ActivityPage = lazy(() => import("./pages/ActivityPage"));
const ImportExportPage = lazy(() => import("./pages/ImportExportPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));
const OrganizationsPage = lazy(() => import("./pages/OrganizationsPage"));
const AttentionPage = lazy(() => import("./pages/AttentionPage"));
const AccountPage = lazy(() => import("./pages/AccountPage"));
const ProjectSettingsPage = lazy(() => import("./pages/ProjectSettingsPage"));
const OnboardingPage = lazy(() => import("./pages/OnboardingPage"));
const DecisionsPage = lazy(() => import("./pages/DecisionsPage"));
const DependenciesPage = lazy(() => import("./pages/DependenciesPage"));
const ForbiddenPage = lazy(() => import("./pages/ForbiddenPage"));
const SuspendedPage = lazy(() => import("./pages/SuspendedPage"));
const SessionExpiredPage = lazy(() => import("./pages/SessionExpiredPage"));
const ForgotPasswordPage = lazy(() => import("./pages/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("./pages/ResetPasswordPage"));
const InvitationPage = lazy(() => import("./pages/InvitationPage"));
const VerifyEmailPage = lazy(() => import("./pages/VerifyEmailPage"));
const SlaPage = lazy(() => import("./pages/SlaPage"));
const JobsPage = lazy(() => import("./pages/JobsPage"));
const SearchPage = lazy(() => import("./pages/SearchPage"));
const DashboardsPage = lazy(() => import("./pages/DashboardsPage"));
const HelpPage = lazy(() => import("./pages/HelpPage"));
const ChangelogPage = lazy(() => import("./pages/ChangelogPage"));
const PortfoliosPage = lazy(() => import("./pages/PortfoliosPage"));
const SharePage = lazy(() => import("./pages/SharePage"));
const PublicIntakePage = lazy(() => import("./pages/PublicIntakePage"));
const ShareLinksPage = lazy(() => import("./pages/ShareLinksPage"));
const ExternalCalendarsPage = lazy(() => import("./pages/ExternalCalendarsPage"));
const WhiteboardsPage = lazy(() => import("./pages/WhiteboardsPage"));
const FocusPage = lazy(() => import("./pages/FocusPage"));
const ProductivityPage = lazy(() => import("./pages/ProductivityPage"));

function Loading() {
  return (
    <Box sx={{ p: { xs: 2, md: 4 } }}>
      <PageSkeleton />
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
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <>{children}</>;
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/app" replace />;
  return <>{children}</>;
}

function TaskDeepLink() {
  const { taskId } = useParams();
  return <TasksPage title="" openTaskId={Number(taskId)} />;
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
  return <TasksPage projectId={id} title={project?.name || ""} />;
}

export default function App() {
  return (
    <AuthProvider>
      <ProjectProvider>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route
              path="/login"
              element={
                <PublicOnly>
                  <LoginPage />
                </PublicOnly>
              }
            />
            <Route
              path="/register"
              element={
                <PublicOnly>
                  <RegisterPage />
                </PublicOnly>
              }
            />
            <Route path="/auth/github/callback" element={<GitHubCallbackPage />} />
            <Route path="/session-expired" element={<SessionExpiredPage />} />
            <Route path="/share/:token" element={<SharePage />} />
            <Route path="/intake/:token" element={<PublicIntakePage />} />
            <Route
              path="/forgot-password"
              element={
                <PublicOnly>
                  <ForgotPasswordPage />
                </PublicOnly>
              }
            />
            <Route
              path="/reset-password"
              element={
                <PublicOnly>
                  <ResetPasswordPage />
                </PublicOnly>
              }
            />
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            <Route
              path="/app"
              element={
                <Protected>
                  <AppLayout />
                </Protected>
              }
            >
              <Route index element={<HomePage />} />
              <Route path="inbox" element={<TasksPage title="" inbox />} />
              <Route path="tasks" element={<TasksPage title="" />} />
              <Route path="favorites" element={<TasksPage title="" favoritesOnly />} />
              <Route path="completed" element={<TasksPage title="" completedOnly />} />
              <Route path="tasks/:taskId" element={<TaskDeepLink />} />
              <Route path="project/:projectId" element={<ProjectOverviewPage />} />
              <Route path="project/:projectId/tasks" element={<ProjectTasks />} />
              <Route
                path="project/:projectId/settings"
                element={<ProjectSettingsPage />}
              />
              <Route path="attention" element={<AttentionPage />} />
              <Route path="invitations/:invitationId" element={<InvitationPage />} />
              <Route path="account" element={<AccountPage />} />
              <Route path="onboarding" element={<OnboardingPage />} />
              <Route path="decisions" element={<DecisionsPage />} />
              <Route path="dependencies" element={<DependenciesPage />} />
              <Route path="403" element={<ForbiddenPage />} />
              <Route path="suspended" element={<SuspendedPage />} />
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
              <Route path="roadmap" element={<RoadmapPage />} />
              <Route path="my-work" element={<MyWorkPage />} />
              <Route path="wiki" element={<WikiPage />} />
              <Route path="okrs" element={<OkrsPage />} />
              <Route path="ai-assistant" element={<AiAssistantPage />} />
              <Route path="projects" element={<ProjectsPage />} />
              <Route path="github" element={<GitHubPage />} />
              <Route path="notifications" element={<NotificationsPage />} />
              <Route path="time-entries" element={<TimeEntriesPage />} />
              <Route path="templates" element={<TaskTemplatesPage />} />
              <Route path="custom-fields" element={<CustomFieldsPage />} />
              <Route path="webhooks" element={<WebhooksPage />} />
              <Route path="feature-flags" element={<FeatureFlagsPage />} />
              <Route path="teams" element={<TeamsPage />} />
              <Route path="offline-sync" element={<OfflineSyncPage />} />
              <Route path="encryption" element={<EncryptionPage />} />
              <Route path="recurrence-rules" element={<RecurrenceRulesPage />} />
              <Route path="backlog" element={<BacklogPage />} />
              <Route path="workflows" element={<WorkflowEditorPage />} />
              <Route path="admin" element={<AdminPage />} />
              <Route path="admin/roles" element={<RolesPage />} />
              <Route path="admin/organizations" element={<OrganizationsPage />} />
              <Route path="admin/sla" element={<SlaPage />} />
              <Route path="admin/jobs" element={<JobsPage />} />
              <Route path="search" element={<SearchPage />} />
              <Route path="dashboards" element={<DashboardsPage />} />
              <Route path="help" element={<HelpPage />} />
              <Route path="changelog" element={<ChangelogPage />} />
              <Route path="trash" element={<TrashPage />} />
              <Route path="meetings" element={<MeetingsPage />} />
              <Route path="risks" element={<RisksPage />} />
              <Route path="intake-forms" element={<IntakeFormsPage />} />
              <Route path="activity" element={<ActivityPage />} />
              <Route path="import-export" element={<ImportExportPage />} />
              <Route path="portfolios" element={<PortfoliosPage />} />
              <Route path="shares" element={<ShareLinksPage />} />
              <Route path="calendars" element={<ExternalCalendarsPage />} />
              <Route path="whiteboards" element={<WhiteboardsPage />} />
              <Route path="whiteboards/:id" element={<WhiteboardsPage />} />
              <Route path="focus" element={<FocusPage />} />
              <Route path="productivity" element={<ProductivityPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/app" replace />} />
          </Routes>
        </Suspense>
      </ProjectProvider>
    </AuthProvider>
  );
}
