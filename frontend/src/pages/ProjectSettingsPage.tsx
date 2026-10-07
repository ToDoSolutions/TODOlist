import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  GridLegacy as Grid,
  Paper,
  Typography,
  Stack,
  TextField,
  Button,
  Divider,
} from "@mui/material";
import {
  KanbanSquare,
  Users,
  Settings,
  Tag,
  Zap,
  Github,
  Archive,
  AlertTriangle,
  FileText,
  Save,
} from "lucide-react";
import PageHeader from "../components/ui/PageHeader";
import DangerZone from "../components/ui/DangerZone";
import { EmptyState } from "../components/ui/states";
import { projectsApi } from "../api/resources";
import { stateLabelsApi } from "../api/featOrg";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import type { TaskState } from "../types";
import { TASK_STATE_I18N_KEYS } from "../i18n/batchTaskUi";

const SECTIONS = [
  {
    titleKey: "p.misc.projectSettings.sectionWorkflow",
    descKey: "p.misc.projectSettings.sectionWorkflowDesc",
    icon: <KanbanSquare size={20} />,
    path: "/app/workflows",
  },
  {
    titleKey: "p.misc.projectSettings.sectionMembers",
    descKey: "p.misc.projectSettings.sectionMembersDesc",
    icon: <Users size={20} />,
    path: "/app/teams",
  },
  {
    titleKey: "nav.customFields",
    descKey: "p.misc.projectSettings.sectionCustomFieldsDesc",
    icon: <Settings size={20} />,
    path: "/app/custom-fields",
  },
  {
    titleKey: "nav.tags",
    descKey: "p.misc.projectSettings.sectionTagsDesc",
    icon: <Tag size={20} />,
    path: "/app/tags",
  },
  {
    titleKey: "nav.automations",
    descKey: "p.misc.projectSettings.sectionAutomationsDesc",
    icon: <Zap size={20} />,
    path: "/app/automations",
  },
  {
    titleKey: "p.misc.projectSettings.sectionIntegrations",
    descKey: "p.misc.projectSettings.sectionIntegrationsDesc",
    icon: <Github size={20} />,
    path: "/app/github",
  },
  {
    titleKey: "nav.templates",
    descKey: "p.misc.projectSettings.sectionTemplatesDesc",
    icon: <FileText size={20} />,
    path: "/app/templates",
  },
  {
    titleKey: "p.misc.projectSettings.sectionImportExport",
    descKey: "p.misc.projectSettings.sectionImportExportDesc",
    icon: <Archive size={20} />,
    path: "/app/import-export",
  },
];

/** Editor de etiquetas personalizadas de estado (columnas del kanban
 * y chips de estado). upsert por (project, state); vacío = quitar el
 * override si existía. */
function StateLabelsSection({ projectId }: { projectId: number }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const states = Object.keys(TASK_STATE_I18N_KEYS) as TaskState[];

  const { data: labels } = useQuery({
    queryKey: ["state-labels", projectId],
    queryFn: () => stateLabelsApi.list(projectId),
  });
  const byState = new Map((labels ?? []).map((l) => [l.state, l]));
  // Borradores locales por estado (empiezan = etiqueta custom o vacío)
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["state-labels", projectId] });

  const commit = useMutation({
    mutationFn: async ({ state, label }: { state: TaskState; label: string }) => {
      const existing = byState.get(state);
      if (!label.trim()) {
        if (existing) await stateLabelsApi.remove(existing.id);
        return;
      }
      await stateLabelsApi.upsert({ project: projectId, state, label: label.trim() });
    },
    onSuccess: invalidate,
    onError: () => notify.error(t("p.misc.projectSettings.saveError")),
  });

  return (
    <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
      <Typography variant="subtitle1" fontWeight={700} mb={1}>
        {t("p.misc.projectSettings.stateLabels")}
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={2}>
        {t("p.misc.projectSettings.stateLabelsDesc")}
      </Typography>
      <Stack spacing={1}>
        {states.map((s) => {
          const custom = byState.get(s);
          const draft = drafts[s] ?? custom?.label ?? "";
          return (
            <Stack key={s} direction="row" spacing={1.5} alignItems="center">
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ width: 110 }}
              >
                {t(TASK_STATE_I18N_KEYS[s])}
              </Typography>
              <TextField
                size="small"
                fullWidth
                placeholder={t(TASK_STATE_I18N_KEYS[s])}
                value={draft}
                onChange={(e) => setDrafts({ ...drafts, [s]: e.target.value })}
                onBlur={() => {
                  if (draft !== (custom?.label ?? ""))
                    commit.mutate({ state: s, label: draft });
                }}
                inputProps={{ maxLength: 50 }}
              />
              {custom && draft !== "" && (
                <Button
                  size="small"
                  variant="text"
                  onClick={() => {
                    setDrafts({ ...drafts, [s]: "" });
                    commit.mutate({ state: s, label: "" });
                  }}
                >
                  {t("p.misc.projectSettings.resetLabel")}
                </Button>
              )}
            </Stack>
          );
        })}
      </Stack>
    </Paper>
  );
}

/**
 * Configuración contextual del proyecto: todo lo que afecta a ESTE proyecto,
 * separado de la administración global del workspace.
 */
export default function ProjectSettingsPage() {
  const { t } = useTranslation();
  const { projectId } = useParams();
  const id = Number(projectId);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const confirm = useConfirm();

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const project = (Array.isArray(projectsData) ? projectsData : []).find(
    (p) => p.id === id,
  );

  const [form, setForm] = useState<{
    name: string;
    description: string;
    color: string;
  } | null>(null);
  const current = form ?? {
    name: project?.name ?? "",
    description: project?.description ?? "",
    color: project?.color ?? "#1976d2",
  };

  const saveMut = useMutation({
    mutationFn: () => projectsApi.update(id, current),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      setForm(null);
      notify.success(t("p.misc.projects.updated"));
    },
    onError: () => notify.error(t("p.misc.projectSettings.saveError")),
  });

  const archiveMut = useMutation({
    mutationFn: () => projectsApi.update(id, { is_archived: !project?.is_archived }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      notify.success(
        project?.is_archived
          ? t("p.misc.projectSettings.restored")
          : t("p.misc.projectSettings.archivedOk"),
      );
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => projectsApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      notify.success(t("p.misc.projects.deleted"));
      navigate("/app/projects");
    },
  });

  if (!project) {
    return (
      <EmptyState
        title={t("p.misc.projectNotFound")}
        description={t("p.misc.projectNotFoundDesc")}
        action={
          <Button onClick={() => navigate("/app/projects")}>
            {t("p.misc.viewProjects")}
          </Button>
        }
      />
    );
  }

  return (
    <Box>
      <PageHeader
        title={t("p.misc.projectSettings.title", { name: project.name })}
        description={t("p.misc.projectSettings.subtitle")}
        breadcrumbs={[
          { label: t("nav.projects"), to: "/app/projects" },
          { label: project.name, to: `/app/project/${id}` },
          { label: t("p.misc.projectSettings.breadcrumb") },
        ]}
      />

      {/* Nombres de columnas: las etiquetas custom se veían en kanban
          (labelFor) pero no había editor — stateLabelsApi.upsert/remove
          estaba huérfana. */}
      <StateLabelsSection projectId={id} />

      {/* General: edición inline */}
      <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
        <Typography variant="subtitle1" fontWeight={700} mb={2}>
          {t("p.misc.projectSettings.general")}
        </Typography>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={2}
          alignItems="flex-start"
        >
          <TextField
            label={t("common.name")}
            size="small"
            sx={{ minWidth: 220 }}
            value={current.name}
            onChange={(e) => setForm({ ...current, name: e.target.value })}
          />
          <TextField
            label={t("p.misc.description")}
            size="small"
            sx={{ flex: 1, minWidth: 220 }}
            value={current.description}
            onChange={(e) => setForm({ ...current, description: e.target.value })}
          />
          <TextField
            label={t("common.color")}
            type="color"
            size="small"
            sx={{ width: 90 }}
            InputLabelProps={{ shrink: true }}
            value={current.color}
            onChange={(e) => setForm({ ...current, color: e.target.value })}
          />
          <Button
            variant="contained"
            startIcon={<Save size={15} />}
            disabled={!form || !current.name.trim() || saveMut.isPending}
            onClick={() => saveMut.mutate()}
          >
            {t("common.save")}
          </Button>
        </Stack>
      </Paper>

      <Grid container spacing={2} mb={3}>
        {SECTIONS.map((s) => (
          <Grid item xs={12} sm={6} md={4} key={s.path + s.titleKey}>
            <Paper
              variant="outlined"
              sx={{
                p: 2,
                cursor: "pointer",
                "&:hover": { borderColor: "primary.main" },
                height: "100%",
              }}
              onClick={() => navigate(s.path)}
              role="link"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && navigate(s.path)}
            >
              <Stack direction="row" spacing={1.5} alignItems="flex-start">
                <Box color="primary.main" mt={0.25}>
                  {s.icon}
                </Box>
                <Box>
                  <Typography variant="subtitle2" fontWeight={700}>
                    {t(s.titleKey)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {t(s.descKey)}
                  </Typography>
                </Box>
              </Stack>
            </Paper>
          </Grid>
        ))}
      </Grid>

      <Divider sx={{ my: 3 }} />
      <DangerZone>
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap>
          <Box flex={1} minWidth={220}>
            <Typography variant="body2" fontWeight={600}>
              {project.is_archived
                ? t("p.misc.projectSettings.restoreProject")
                : t("p.misc.projectSettings.archiveProject")}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {project.is_archived
                ? t("p.misc.projectSettings.restoreDesc")
                : t("p.misc.projectSettings.archiveDesc")}
            </Typography>
          </Box>
          <Button
            variant="outlined"
            color="warning"
            size="small"
            onClick={() => archiveMut.mutate()}
            disabled={archiveMut.isPending}
          >
            {project.is_archived
              ? t("p.misc.projectSettings.restore")
              : t("p.misc.projectSettings.archive")}
          </Button>
        </Stack>
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap>
          <Box flex={1} minWidth={220}>
            <Typography variant="body2" fontWeight={600}>
              {t("p.misc.deleteProject")}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {t("p.misc.projectSettings.deleteDesc")}
            </Typography>
          </Box>
          <Button
            variant="outlined"
            color="error"
            size="small"
            startIcon={<AlertTriangle size={14} />}
            onClick={async () => {
              if (
                await confirm(
                  t("p.misc.projectSettings.confirmDelete", {
                    name: project.name,
                  }),
                  { confirmLabel: t("common.delete") },
                )
              )
                deleteMut.mutate();
            }}
            disabled={deleteMut.isPending}
          >
            {t("common.delete")}
          </Button>
        </Stack>
      </DangerZone>
    </Box>
  );
}
