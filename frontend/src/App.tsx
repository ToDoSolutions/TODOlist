import { Routes, Route, Navigate, useLocation, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CircularProgress, Box } from "@mui/material";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import AppLayout from "./pages/AppLayout";
import TasksPage from "./pages/TasksPage";
import { projectsApi } from "./api/resources";

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
    select: (list) => list.find((p) => p.id === id),
  });
  return <TasksPage projectId={id} title={project?.name || "Proyecto"} />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
        <Route path="/register" element={<PublicOnly><RegisterPage /></PublicOnly>} />
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
        </Route>
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </AuthProvider>
  );
}
