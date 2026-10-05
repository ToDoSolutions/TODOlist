import { useState } from "react";
import { CardGridSkeleton } from "../components/ui/skeletons";
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
  Autocomplete,
} from "@mui/material";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Briefcase } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState, ErrorState } from "../components/ui/states";
import { useConfirm } from "../components/ConfirmDialog";
import { projectsApi } from "../api/resources";
import { portfoliosApi, type Portfolio } from "../api/featOrg";
import type { Project } from "../types";
import { notify } from "../notify";
import "../i18n";

interface PortfolioForm {
  name: string;
  color: string;
  project_ids: number[];
}

const emptyForm: PortfolioForm = {
  name: "",
  color: "#1976d2",
  project_ids: [],
};

/**
 * Portafolios: agrupaciones de proyectos con color propio. Los chips de
 * cada proyecto enlazan a su vista de detalle.
 */
export default function PortfoliosPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const confirm = useConfirm();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Portfolio | null>(null);
  const [form, setForm] = useState<PortfolioForm>(emptyForm);

  const {
    data: portfolios = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["portfolios"],
    queryFn: portfoliosApi.list,
  });

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData) ? projectsData : [];

  const saveMut = useMutation({
    mutationFn: () =>
      editing ? portfoliosApi.update(editing.id, form) : portfoliosApi.create(form),
    onSuccess: () => {
      notify.success(
        editing ? t("p.org.portfolios.updated") : t("p.org.portfolios.created"),
      );
      qc.invalidateQueries({ queryKey: ["portfolios"] });
      closeDialog();
    },
    onError: () =>
      notify.error(
        editing ? t("p.org.portfolios.updateError") : t("p.org.portfolios.createError"),
      ),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => portfoliosApi.remove(id),
    onSuccess: () => {
      notify.info(t("p.org.portfolios.deleted"));
      qc.invalidateQueries({ queryKey: ["portfolios"] });
    },
    onError: () => notify.error(t("p.org.portfolios.deleteError")),
  });

  const closeDialog = () => {
    setDialogOpen(false);
    setEditing(null);
    setForm(emptyForm);
  };

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setDialogOpen(true);
  };

  const openEdit = (p: Portfolio) => {
    setEditing(p);
    setForm({
      name: p.name,
      color: p.color,
      project_ids: p.project_ids ?? [],
    });
    setDialogOpen(true);
  };

  const handleDelete = async (p: Portfolio) => {
    if (
      await confirm(t("p.org.portfolios.deleteConfirm", { name: p.name }), {
        danger: true,
        confirmLabel: t("common.delete"),
      })
    ) {
      deleteMut.mutate(p.id);
    }
  };

  const projectById = (id: number): Project | undefined =>
    projects.find((p) => p.id === id);

  return (
    <Box maxWidth={1100} mx="auto">
      <PageHeader
        title={t("p.org.portfolios.title")}
        description={t("p.org.portfolios.description")}
        breadcrumbs={[
          { label: t("nav.projects"), to: "/app/projects" },
          { label: t("p.org.portfolios.title") },
        ]}
        actions={
          <Button variant="contained" startIcon={<Plus size={18} />} onClick={openCreate}>
            {t("p.org.portfolios.new")}
          </Button>
        }
      />

      {isLoading && <CardGridSkeleton />}

      {error && !isLoading && (
        <ErrorState
          title={t("p.org.portfolios.loadError")}
          onRetry={() => void refetch()}
        />
      )}

      {!isLoading && portfolios.length === 0 && !error && (
        <EmptyState
          title={t("p.org.portfolios.empty")}
          description={t("p.org.portfolios.emptyDesc")}
          action={
            <Button variant="contained" onClick={openCreate}>
              {t("p.org.portfolios.createFirst")}
            </Button>
          }
        />
      )}

      {!isLoading && portfolios.length > 0 && (
        <Stack spacing={1.5}>
          {portfolios.map((portfolio) => (
            <Paper key={portfolio.id} variant="outlined" sx={{ p: 2 }}>
              <Stack
                direction={{ xs: "column", sm: "row" }}
                spacing={1.5}
                alignItems={{ sm: "center" }}
              >
                <Stack
                  direction="row"
                  spacing={1.5}
                  alignItems="center"
                  minWidth={0}
                  flex={1}
                >
                  <Briefcase
                    size={22}
                    color={portfolio.color}
                    style={{ flexShrink: 0 }}
                  />
                  <Typography variant="subtitle1" fontWeight={700} noWrap>
                    {portfolio.name}
                  </Typography>
                  <Box
                    sx={{
                      width: 14,
                      height: 14,
                      borderRadius: "50%",
                      bgcolor: portfolio.color,
                      border: "1px solid rgba(0,0,0,0.1)",
                      flexShrink: 0,
                    }}
                  />
                  <Chip
                    size="small"
                    variant="outlined"
                    label={t("p.org.portfolios.projectsCount", {
                      count: portfolio.project_ids?.length ?? 0,
                    })}
                  />
                </Stack>

                <Stack
                  direction="row"
                  spacing={0.5}
                  alignItems="center"
                  flexWrap="wrap"
                  useFlexGap
                >
                  {(portfolio.project_ids ?? []).map((pid) => {
                    const proj = projectById(pid);
                    return (
                      <Chip
                        key={pid}
                        size="small"
                        clickable
                        onClick={() => navigate(`/app/project/${pid}`)}
                        label={proj?.name ?? `#${pid}`}
                        sx={
                          proj
                            ? {
                                borderLeft: `3px solid ${proj.color}`,
                              }
                            : undefined
                        }
                      />
                    );
                  })}
                </Stack>

                <Stack direction="row" spacing={0.5} flexShrink={0}>
                  <Tooltip title={t("common.edit")}>
                    <IconButton size="small" onClick={() => openEdit(portfolio)}>
                      <Pencil size={16} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title={t("common.delete")}>
                    <IconButton
                      size="small"
                      onClick={() => handleDelete(portfolio)}
                      disabled={deleteMut.isPending}
                    >
                      <Trash2 size={16} />
                    </IconButton>
                  </Tooltip>
                </Stack>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      {/* Create / edit dialog */}
      <Dialog open={dialogOpen} onClose={closeDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editing ? t("p.org.portfolios.edit") : t("p.org.portfolios.new")}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("common.name")}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
              autoFocus
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
            <Autocomplete
              multiple
              options={projects}
              getOptionLabel={(p) => p.name}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              value={projects.filter((p) => form.project_ids.includes(p.id))}
              onChange={(_, v) => setForm({ ...form, project_ids: v.map((p) => p.id) })}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label={t("p.org.portfolios.projects")}
                  placeholder={t("p.org.portfolios.selectProjects")}
                />
              )}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDialog}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => saveMut.mutate()}
            disabled={!form.name.trim() || saveMut.isPending}
          >
            {editing ? t("common.save") : t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}