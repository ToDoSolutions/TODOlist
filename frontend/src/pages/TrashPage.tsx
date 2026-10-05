import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Stack,
  Paper,
  Button,
  Tabs,
  Tab,
  Chip,
  Divider,
} from "@mui/material";
import { Archive, RotateCcw, Trash2 } from "lucide-react";
import { formatDate } from "../lib/dates";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/states";
import { projectsApi, tasksApi } from "../api/resources";
import { notify } from "../notify";

import { useState } from "react";

/**
 * Archivo / papelera: contenido fuera del trabajo activo.
 * Archivado ≠ eliminado: restaurable, con registro de quién archivó.
 */
export default function TrashPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [tab, setTab] = useState(0);

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const archivedProjects = (Array.isArray(projectsData) ? projectsData : []).filter(
    (p) => p.is_archived,
  );

  const { data: tasksData } = useQuery({
    queryKey: ["tasks", { state: "archived" }],
    queryFn: () => tasksApi.list({ state: "archived" }),
  });
  const archivedTasks = Array.isArray(tasksData) ? tasksData : [];

  const restoreProject = useMutation({
    mutationFn: (id: number) => projectsApi.update(id, { is_archived: false }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      notify.success(t("p.work.trash.projectRestored"));
    },
  });

  const restoreTask = useMutation({
    mutationFn: (id: number) => tasksApi.update(id, { state: "backlog" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      notify.success(t("p.work.trash.taskRestored"));
    },
  });

  return (
    <Box>
      <PageHeader
        title={t("p.work.trash.title")}
        description={t("p.work.trash.desc")}
        breadcrumbs={[
          { label: t("p.work.trash.breadcrumbAdmin"), to: "/app/admin" },
          { label: t("p.work.trash.title") },
        ]}
      />

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
        <Tab
          label={t("p.work.trash.archivedProjects", {
            count: archivedProjects.length,
          })}
        />
        <Tab
          label={t("p.work.trash.archivedTasks", {
            count: archivedTasks.length,
          })}
        />
      </Tabs>

      {tab === 0 &&
        (archivedProjects.length === 0 ? (
          <EmptyState
            title={t("p.work.trash.noProjects")}
            description={t("p.work.trash.noProjectsDesc")}
          />
        ) : (
          <Stack spacing={1}>
            {archivedProjects.map((p) => (
              <Paper
                key={p.id}
                variant="outlined"
                sx={{ p: 1.5, display: "flex", alignItems: "center", gap: 2 }}
              >
                <Archive size={18} color={p.color} />
                <Box flex={1}>
                  <Typography variant="body2" fontWeight={600}>
                    {p.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {t("p.work.trash.archivedOn", {
                      date: formatDate(p.updated_at),
                    })}
                  </Typography>
                </Box>
                <Button
                  size="small"
                  startIcon={<RotateCcw size={14} />}
                  onClick={() => restoreProject.mutate(p.id)}
                  disabled={restoreProject.isPending}
                >
                  {t("p.work.trash.restore")}
                </Button>
              </Paper>
            ))}
          </Stack>
        ))}

      {tab === 1 &&
        (archivedTasks.length === 0 ? (
          <EmptyState
            title={t("p.work.trash.noTasks")}
            description={t("p.work.trash.noTasksDesc")}
          />
        ) : (
          <Stack spacing={1}>
            {archivedTasks.map((task) => (
              <Paper
                key={task.id}
                variant="outlined"
                sx={{ p: 1.5, display: "flex", alignItems: "center", gap: 2 }}
              >
                <Trash2 size={16} />
                <Box flex={1}>
                  <Typography variant="body2" fontWeight={600}>
                    {task.title}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {task.due_date
                      ? t("p.work.trash.dueOn", {
                          date: formatDate(task.due_date),
                        })
                      : t("p.work.home.noDate")}
                  </Typography>
                </Box>
                <Chip size="small" label={t("task.state.archived")} variant="outlined" />
                <Button
                  size="small"
                  startIcon={<RotateCcw size={14} />}
                  onClick={() => restoreTask.mutate(task.id)}
                  disabled={restoreTask.isPending}
                >
                  {t("p.work.trash.restore")}
                </Button>
              </Paper>
            ))}
          </Stack>
        ))}

      <Divider sx={{ my: 3 }} />
      <Typography variant="caption" color="text.secondary">
        {t("p.work.trash.footer")}
      </Typography>
    </Box>
  );
}
