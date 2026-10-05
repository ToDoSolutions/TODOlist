import { useState } from "react";
import {
  Box,
  Typography,
  Paper,
  Button,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
  Chip,
  IconButton,
  Tooltip,
  Grid,
  MenuItem,
  CircularProgress,
  Checkbox,
  FormControlLabel,
} from "@mui/material";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Pencil,
  Trash2,
  Folder,
  LayoutTemplate,
  BookmarkPlus,
  Star,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { projectsApi } from "../api/resources";
import { projectTemplatesApi } from "../api/featOrg";
import { HEALTH_SX_COLORS, type ProjectHealthFields } from "../api/featComp";
import { formatDate } from "../lib/dates";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState, ErrorState } from "../components/ui/states";
import { CardGridSkeleton } from "../components/ui/skeletons";
import type { Project } from "../types";
import { notify } from "../notify";
import "../i18n";

interface ProjectForm {
  name: string;
  description: string;
  color: string;
}

const emptyForm: ProjectForm = {
  name: "",
  description: "",
  color: "#1976d2",
};

export default function ProjectsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<ProjectForm>(emptyForm);

  // Plantillas de proyecto
  const [tplDialogOpen, setTplDialogOpen] = useState(false);
  const [tplId, setTplId] = useState<number | "">("");
  const [tplForm, setTplForm] = useState({ name: "", description: "" });
  const [saveTplProject, setSaveTplProject] = useState<Project | null>(null);
  const [tplName, setTplName] = useState("");
  const [tplPublic, setTplPublic] = useState(false);

  const {
    data: projects = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });

  // Favoritos primero (acceso rápido estilo Jira/Asana starred).
  const sortedProjects = [...projects].sort(
    (a, b) => Number(b.is_favorite ?? false) - Number(a.is_favorite ?? false),
  );

  const favMut = useMutation({
    mutationFn: (p: Project) =>
      p.is_favorite ? projectsApi.unfavorite(p.id) : projectsApi.favorite(p.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
    onError: () => notify.error(t("p.misc.projects.updateError")),
  });

  const createMut = useMutation({
    mutationFn: () => projectsApi.create(form),
    onSuccess: () => {
      notify.success(t("p.misc.projects.created"));
      qc.invalidateQueries({ queryKey: ["projects"] });
      setDialogOpen(false);
      setForm(emptyForm);
    },
    onError: () => notify.error(t("p.misc.projects.createError")),
  });

  const updateMut = useMutation({
    mutationFn: () => projectsApi.update(editingId!, form),
    onSuccess: () => {
      notify.success(t("p.misc.projects.updated"));
      qc.invalidateQueries({ queryKey: ["projects"] });
      setEditOpen(false);
      setEditingId(null);
      setForm(emptyForm);
    },
    onError: () => notify.error(t("p.misc.projects.updateError")),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => projectsApi.remove(id),
    onSuccess: () => {
      notify.info(t("p.misc.projects.deleted"));
      qc.invalidateQueries({ queryKey: ["projects"] });
      setDeleteId(null);
    },
    onError: () => notify.error(t("p.misc.projects.deleteError")),
  });

  // Se cargan solo al abrir el diálogo (lista corta, incluye builtin).
  const { data: templates = [] } = useQuery({
    queryKey: ["project-templates"],
    queryFn: () => projectTemplatesApi.list(),
    enabled: tplDialogOpen,
  });
  const selectedTpl = templates.find((tpl) => tpl.id === tplId);

  const applyTplMut = useMutation({
    mutationFn: () =>
      projectTemplatesApi.apply(tplId as number, {
        name: tplForm.name,
        description: tplForm.description || undefined,
      }),
    onSuccess: (res) => {
      notify.success(t("p.org.templates.applied", { count: res.tasks_created }));
      qc.invalidateQueries({ queryKey: ["projects"] });
      setTplDialogOpen(false);
      setTplId("");
      setTplForm({ name: "", description: "" });
      navigate(`/app/project/${res.project_id}`);
    },
    onError: () => notify.error(t("p.org.templates.applyError")),
  });

  const saveTplMut = useMutation({
    mutationFn: () =>
      projectTemplatesApi.fromProject({
        project_id: saveTplProject!.id,
        name: tplName,
        public: tplPublic,
      }),
    onSuccess: () => {
      notify.success(t("p.org.templates.saved"));
      qc.invalidateQueries({ queryKey: ["project-templates"] });
      setSaveTplProject(null);
      setTplName("");
      setTplPublic(false);
    },
    onError: () => notify.error(t("p.org.templates.saveError")),
  });

  // Publicar/retirar del catálogo comunitario (solo plantillas propias)
  const publishTplMut = useMutation({
    mutationFn: ({ id, isPublic }: { id: number; isPublic: boolean }) =>
      projectTemplatesApi.update(id, { is_public: isPublic }),
    onSuccess: (_r, v) => {
      notify.success(
        v.isPublic
          ? t("p.org.templates.published")
          : t("p.org.templates.unpublished"),
      );
      qc.invalidateQueries({ queryKey: ["project-templates"] });
    },
    onError: () => notify.error(t("p.org.templates.saveError")),
  });

  const openEdit = (project: Project) => {
    setEditingId(project.id);
    setForm({
      name: project.name,
      description: project.description,
      color: project.color,
    });
    setEditOpen(true);
  };

  const projectToDelete = projects.find((p) => p.id === deleteId);

  return (
    <Box maxWidth={1100} mx="auto">
      <PageHeader
        title={t("nav.projects")}
        actions={
          <>
            <Button
              variant="outlined"
              startIcon={<LayoutTemplate size={18} />}
              onClick={() => setTplDialogOpen(true)}
            >
              {t("p.org.templates.newFromTemplate")}
            </Button>
            <Button
              variant="contained"
              startIcon={<Plus size={18} />}
              onClick={() => {
                setForm(emptyForm);
                setDialogOpen(true);
              }}
            >
              {t("p.misc.projects.new")}
            </Button>
          </>
        }
      />

      {isLoading && <CardGridSkeleton cards={6} />}

      {error && !isLoading && (
        <ErrorState
          title={t("p.misc.projects.loadError")}
          onRetry={() => void refetch()}
        />
      )}

      {!isLoading && projects.length === 0 && !error && (
        <EmptyState
          title={t("p.misc.projects.emptyTitle")}
          description={t("p.misc.projects.empty")}
          action={
            <Button
              variant="contained"
              startIcon={<Plus size={18} />}
              onClick={() => {
                setForm(emptyForm);
                setDialogOpen(true);
              }}
            >
              {t("p.misc.projects.new")}
            </Button>
          }
        />
      )}

      {!isLoading && projects.length > 0 && (
        <Grid container spacing={2}>
          {sortedProjects.map((project) => {
            const health = (project as Partial<ProjectHealthFields>).health;
            // El serializer de Project no expone conteos de completadas
            // (solo tasks_count/sprints_count/epics_count); el "status"
            // disponible es latest_status_update (health + nota + fecha).
            const statusUpdate = (project as Partial<ProjectHealthFields>)
              .latest_status_update;
            return (
              <Grid key={project.id} item xs={12} sm={6} md={4}>
                <Paper
                  variant="outlined"
                  onClick={() => navigate(`/app/project/${project.id}`)}
                  sx={{
                    p: 2,
                    cursor: "pointer",
                    height: "100%",
                    transition: "all 0.2s ease",
                    "&:hover": {
                      borderColor: project.color,
                      boxShadow: 3,
                    },
                  }}
                >
                  <Stack direction="row" alignItems="flex-start" spacing={1.5}>
                    <Folder
                      size={24}
                      color={project.color}
                      style={{ flexShrink: 0, marginTop: 2 }}
                    />
                    <Box flex={1} minWidth={0}>
                      <Stack
                        direction="row"
                        alignItems="center"
                        justifyContent="space-between"
                      >
                        <Typography
                          variant="h6"
                          title={project.name}
                          sx={{
                            fontWeight: 600,
                            display: "-webkit-box",
                            WebkitBoxOrient: "vertical",
                            WebkitLineClamp: 2,
                            overflow: "hidden",
                            lineHeight: 1.25,
                          }}
                        >
                          {project.name}
                        </Typography>
                        <Stack
                          direction="row"
                          spacing={0.5}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Tooltip
                            title={
                              project.is_favorite
                                ? t("p.taskx.unfavorite")
                                : t("p.taskx.favorite")
                            }
                          >
                            <IconButton
                              size="small"
                              onClick={() => favMut.mutate(project)}
                              aria-label={t("p.taskx.favorite")}
                            >
                              <Star
                                size={16}
                                color="#f5a623"
                                fill={project.is_favorite ? "#f5a623" : "none"}
                              />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title={t("common.edit")}>
                            <IconButton size="small" onClick={() => openEdit(project)}>
                              <Pencil size={16} />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title={t("p.org.templates.saveAsTemplate")}>
                            <IconButton
                              size="small"
                              onClick={() => {
                                setSaveTplProject(project);
                                setTplName(project.name);
                              }}
                            >
                              <BookmarkPlus size={16} />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title={t("common.delete")}>
                            <IconButton
                              size="small"
                              onClick={() => setDeleteId(project.id)}
                            >
                              <Trash2 size={16} />
                            </IconButton>
                          </Tooltip>
                        </Stack>
                      </Stack>

                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{
                          mt: 0.5,
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                          minHeight: 40,
                        }}
                      >
                        {project.description || t("p.misc.noDescription")}
                      </Typography>

                      {statusUpdate && (
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          display="block"
                          noWrap
                          sx={{ mt: 0.5 }}
                          title={statusUpdate.note || undefined}
                        >
                          {statusUpdate.note || t(`p.org.health.${statusUpdate.health}`)}
                          {" · "}
                          {formatDate(statusUpdate.created_at)}
                        </Typography>
                      )}

                      <Stack
                        direction="row"
                        alignItems="center"
                        spacing={1}
                        sx={{ mt: 1.5 }}
                      >
                        {(() => {
                          const total = project.tasks_count ?? 0;
                          const done = project.completed_tasks_count ?? 0;
                          const pct = total > 0 ? Math.round((done / total) * 100) : 0;
                          return (
                            <Tooltip
                              title={t("p.misc.projectsProgress", {
                                done,
                                total,
                              })}
                            >
                              <Box
                                sx={{
                                  position: "relative",
                                  display: "inline-flex",
                                  alignItems: "center",
                                }}
                                aria-label={t("p.misc.projectsProgress", {
                                  done,
                                  total,
                                })}
                              >
                                <CircularProgress
                                  variant="determinate"
                                  value={pct}
                                  size={24}
                                  color={pct === 100 ? "success" : "primary"}
                                />
                                <Typography
                                  variant="caption"
                                  sx={{
                                    position: "absolute",
                                    fontSize: 9,
                                    fontWeight: 700,
                                  }}
                                >
                                  {pct}
                                </Typography>
                              </Box>
                            </Tooltip>
                          );
                        })()}
                        <Chip
                          size="small"
                          label={t("p.misc.tasksCount", {
                            count: project.tasks_count ?? 0,
                          })}
                          variant="outlined"
                        />
                        <Chip
                          size="small"
                          label={t("p.misc.sprintsCount", {
                            count: project.sprints_count ?? 0,
                          })}
                          variant="outlined"
                        />
                        <Chip
                          size="small"
                          label={t("p.misc.epicsCount", {
                            count: project.epics_count ?? 0,
                          })}
                          variant="outlined"
                        />
                        {project.is_archived && (
                          <Chip
                            size="small"
                            label={t("p.misc.projects.archived")}
                            color="default"
                          />
                        )}
                        {health && (
                          <Tooltip
                            title={`${t("p.org.health.label")}: ${t(
                              `p.org.health.${health}`,
                            )}`}
                          >
                            <Box
                              sx={{
                                width: 10,
                                height: 10,
                                borderRadius: "50%",
                                bgcolor: HEALTH_SX_COLORS[health],
                                flexShrink: 0,
                              }}
                            />
                          </Tooltip>
                        )}
                        <Box
                          sx={{
                            width: 14,
                            height: 14,
                            borderRadius: "50%",
                            bgcolor: project.color,
                            ml: "auto",
                            border: "1px solid rgba(0,0,0,0.1)",
                          }}
                        />
                      </Stack>
                    </Box>
                  </Stack>
                </Paper>
              </Grid>
            );
          })}
        </Grid>
      )}

      {/* Create dialog */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.misc.projects.new")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("common.name")}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
              autoFocus
            />
            <TextField
              label={t("p.misc.description")}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              fullWidth
              multiline
              rows={3}
            />
            <Stack direction="row" alignItems="center" spacing={2}>
              <Typography variant="body2">{t("common.color")}:</Typography>
              <input
                type="color"
                value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
                style={{ width: 50, height: 30, border: "none", cursor: "pointer" }}
              />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => createMut.mutate()}
            disabled={!form.name || createMut.isPending}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t("p.misc.projects.edit")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("common.name")}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
              autoFocus
            />
            <TextField
              label={t("p.misc.description")}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              fullWidth
              multiline
              rows={3}
            />
            <Stack direction="row" alignItems="center" spacing={2}>
              <Typography variant="body2">{t("common.color")}:</Typography>
              <input
                type="color"
                value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
                style={{ width: 50, height: 30, border: "none", cursor: "pointer" }}
              />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => updateMut.mutate()}
            disabled={!form.name || updateMut.isPending}
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteId !== null}
        onClose={() => setDeleteId(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>{t("p.misc.deleteProject")}</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            {t("p.misc.projects.confirmDelete", {
              name: projectToDelete?.name ?? t("p.misc.projects.thisProject"),
            })}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteId(null)}>{t("common.cancel")}</Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => deleteId && deleteMut.mutate(deleteId)}
            disabled={deleteMut.isPending}
          >
            {t("common.delete")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Create from template dialog */}
      <Dialog
        open={tplDialogOpen}
        onClose={() => setTplDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.org.templates.dialogTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              select
              label={t("p.org.templates.template")}
              value={tplId}
              onChange={(e) => setTplId(Number(e.target.value))}
              fullWidth
              autoFocus
            >
              <MenuItem value="" disabled>
                {templates.length === 0
                  ? t("p.org.templates.empty")
                  : t("p.org.templates.template")}
              </MenuItem>
              {templates.map((tpl) => (
                <MenuItem key={tpl.id} value={tpl.id}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <span>{tpl.name}</span>
                    {tpl.is_builtin && (
                      <Chip
                        size="small"
                        color="primary"
                        variant="outlined"
                        label={t("p.org.templates.builtin")}
                      />
                    )}
                    {tpl.is_public && !tpl.is_builtin && !tpl.is_mine && (
                      <Chip
                        size="small"
                        color="secondary"
                        variant="outlined"
                        label={t("p.org.templates.community")}
                      />
                    )}
                    <Chip
                      size="small"
                      variant="outlined"
                      label={t("p.org.templates.tasksCount", {
                        count: tpl.config?.tasks?.length ?? 0,
                      })}
                    />
                  </Stack>
                </MenuItem>
              ))}
            </TextField>
            {selectedTpl?.description && (
              <Typography variant="body2" color="text.secondary">
                {selectedTpl.description}
              </Typography>
            )}
            {selectedTpl && (selectedTpl.author || (selectedTpl.use_count ?? 0) > 0) && (
              <Typography variant="caption" color="text.secondary">
                {selectedTpl.author && `${selectedTpl.author} · `}
                {(selectedTpl.use_count ?? 0) > 0 &&
                  t("p.org.templates.uses", { count: selectedTpl.use_count })}
              </Typography>
            )}
            {selectedTpl?.is_mine && !selectedTpl.is_builtin && (
              <FormControlLabel
                control={
                  <Checkbox
                    checked={!!selectedTpl.is_public}
                    onChange={(e) =>
                      publishTplMut.mutate({
                        id: selectedTpl.id,
                        isPublic: e.target.checked,
                      })
                    }
                    size="small"
                  />
                }
                label={t("p.org.templates.publish")}
              />
            )}
            {selectedTpl && (selectedTpl.config?.tasks?.length ?? 0) > 0 && (
              <Box>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  {t("p.org.templates.preview")}
                </Typography>
                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap mt={0.5}>
                  {selectedTpl.config.tasks.slice(0, 6).map((task, i) => (
                    <Chip key={i} size="small" variant="outlined" label={task.title} />
                  ))}
                  {selectedTpl.config.tasks.length > 6 && (
                    <Chip
                      size="small"
                      variant="outlined"
                      label={`+${selectedTpl.config.tasks.length - 6}`}
                    />
                  )}
                </Stack>
              </Box>
            )}
            <TextField
              label={t("common.name")}
              value={tplForm.name}
              onChange={(e) => setTplForm({ ...tplForm, name: e.target.value })}
              fullWidth
            />
            <TextField
              label={t("p.misc.description")}
              value={tplForm.description}
              onChange={(e) => setTplForm({ ...tplForm, description: e.target.value })}
              fullWidth
              multiline
              rows={3}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTplDialogOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => applyTplMut.mutate()}
            disabled={!tplId || !tplForm.name.trim() || applyTplMut.isPending}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Save project as template dialog */}
      <Dialog
        open={saveTplProject !== null}
        onClose={() => setSaveTplProject(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>{t("p.org.templates.saveDialogTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {t("p.org.templates.saveDialogDesc")}
            </Typography>
            <TextField
              label={t("p.org.templates.templateName")}
              value={tplName}
              onChange={(e) => setTplName(e.target.value)}
              fullWidth
              autoFocus
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={tplPublic}
                  onChange={(e) => setTplPublic(e.target.checked)}
                  size="small"
                />
              }
              label={
                <>
                  {t("p.org.templates.publish")}
                  <Typography variant="caption" display="block" color="text.secondary">
                    {t("p.org.templates.publishHint")}
                  </Typography>
                </>
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSaveTplProject(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => saveTplMut.mutate()}
            disabled={!tplName.trim() || saveTplMut.isPending}
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
