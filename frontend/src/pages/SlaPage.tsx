import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Paper,
  Stack,
  Chip,
  Button,
  Switch,
  IconButton,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Alert,
  CircularProgress,
  Tooltip,
  FormControlLabel,
  Checkbox,
} from "@mui/material";
import { Timer, Plus, Pencil, Trash2, AlertTriangle } from "lucide-react";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/states";
import { slaPoliciesApi, tasksApi, type SlaPolicy } from "../api/resources";
import { PRIORITY_LABELS, type TaskPriority } from "../types";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";

/** Gestión de políticas SLA y tareas que han incumplido su objetivo. */
export default function SlaPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<SlaPolicy | "new" | null>(null);
  const [form, setForm] = useState<Partial<SlaPolicy>>({});

  const { data: policies, isLoading } = useQuery({
    queryKey: ["sla-policies"],
    queryFn: slaPoliciesApi.list,
  });
  const list = Array.isArray(policies) ? policies : [];

  const { data: breached } = useQuery({
    queryKey: ["tasks", "sla-breached"],
    queryFn: () => tasksApi.list({ sla_breached: "true" }),
  });
  const breachedTasks = Array.isArray(breached) ? breached : [];

  const saveMut = useMutation({
    mutationFn: (p: Partial<SlaPolicy>) =>
      dialog === "new"
        ? slaPoliciesApi.create(p)
        : slaPoliciesApi.update((dialog as SlaPolicy).id, p),
    onSuccess: () => {
      notify.success(t("p.admin.sla.saved"));
      qc.invalidateQueries({ queryKey: ["sla-policies"] });
      setDialog(null);
    },
    onError: () => notify.error(t("p.admin.sla.errorSave")),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => slaPoliciesApi.remove(id),
    onSuccess: () => {
      notify.success(t("p.admin.sla.deleted"));
      qc.invalidateQueries({ queryKey: ["sla-policies"] });
    },
  });

  const toggleMut = useMutation({
    mutationFn: (p: SlaPolicy) => slaPoliciesApi.update(p.id, { enabled: !p.enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sla-policies"] }),
  });

  const openDialog = (p: SlaPolicy | "new") => {
    setDialog(p);
    setForm(
      p === "new"
        ? {
            name: "",
            priority: 3,
            response_hours: 24,
            resolution_hours: 72,
            bump_priority: true,
            notify_owner: true,
            notify_assignee: true,
          }
        : { ...p },
    );
  };

  return (
    <Box>
      <PageHeader
        title={t("p.admin.sla.title")}
        description={t("p.admin.sla.description")}
        breadcrumbs={[
          { label: t("p.admin.breadcrumb"), to: "/app/admin" },
          { label: t("p.admin.sla.title") },
        ]}
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={15} />}
            onClick={() => openDialog("new")}
          >
            {t("p.admin.sla.newPolicy")}
          </Button>
        }
      />

      {isLoading ? (
        <CircularProgress />
      ) : list.length === 0 ? (
        <EmptyState
          title={t("p.admin.sla.emptyTitle")}
          description={t("p.admin.sla.emptyDesc")}
        />
      ) : (
        <Paper variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t("p.admin.sla.colPolicy")}</TableCell>
                <TableCell>{t("p.admin.sla.colPriority")}</TableCell>
                <TableCell>{t("p.admin.sla.colResponse")}</TableCell>
                <TableCell>{t("p.admin.sla.colResolution")}</TableCell>
                <TableCell>{t("p.admin.sla.colActions")}</TableCell>
                <TableCell>{t("p.admin.sla.colActive")}</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {list.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>{p.name}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={PRIORITY_LABELS[p.priority] ?? `P${p.priority}`}
                    />
                  </TableCell>
                  <TableCell>{p.response_hours}h</TableCell>
                  <TableCell>{p.resolution_hours}h</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      {p.bump_priority && (
                        <Chip
                          size="small"
                          variant="outlined"
                          label={t("p.admin.sla.chipBump")}
                        />
                      )}
                      {p.notify_owner && (
                        <Chip
                          size="small"
                          variant="outlined"
                          label={t("p.admin.sla.chipNotify")}
                        />
                      )}
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Switch
                      size="small"
                      checked={p.enabled}
                      onChange={() => toggleMut.mutate(p)}
                      inputProps={{
                        "aria-label": t("p.admin.sla.ariaEnable", { name: p.name }),
                      }}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      size="small"
                      onClick={() => openDialog(p)}
                      aria-label={t("p.admin.sla.ariaEdit", { name: p.name })}
                    >
                      <Pencil size={15} />
                    </IconButton>
                    <IconButton
                      size="small"
                      color="error"
                      aria-label={t("p.admin.sla.ariaDelete", { name: p.name })}
                      onClick={async () => {
                        if (
                          await confirm(t("p.admin.sla.confirmDelete", { name: p.name }))
                        )
                          deleteMut.mutate(p.id);
                      }}
                    >
                      <Trash2 size={15} />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}

      {/* Tareas que han incumplido el SLA */}
      <Paper variant="outlined" sx={{ p: 2, mt: 3 }}>
        <Stack direction="row" spacing={1} alignItems="center" mb={1.5}>
          <AlertTriangle size={18} color="#d32f2f" />
          <Typography variant="subtitle1" fontWeight={700}>
            {t("p.admin.sla.breachedTitle")}
          </Typography>
          <Chip
            size="small"
            label={breachedTasks.length}
            color="error"
            variant="outlined"
          />
        </Stack>
        {breachedTasks.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {t("p.admin.sla.breachedEmpty")}
          </Typography>
        ) : (
          <Stack spacing={0.5}>
            {breachedTasks.map((task) => (
              <Paper
                key={task.id}
                variant="outlined"
                sx={{ p: 1, cursor: "pointer" }}
                onClick={() => navigate(`/app/tasks/${task.id}`)}
              >
                <Stack direction="row" spacing={1} alignItems="center">
                  <Timer size={14} />
                  <Typography variant="body2" fontWeight={600} sx={{ flex: 1 }}>
                    {task.title}
                  </Typography>
                  <Chip
                    size="small"
                    label={PRIORITY_LABELS[task.priority] ?? `P${task.priority}`}
                  />
                </Stack>
              </Paper>
            ))}
          </Stack>
        )}
      </Paper>

      {/* Crear / editar política */}
      <Dialog open={!!dialog} onClose={() => setDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {dialog === "new" ? t("p.admin.sla.dialogNew") : t("p.admin.sla.dialogEdit")}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField
              label={t("common.name")}
              required
              fullWidth
              value={form.name ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
            <TextField
              select
              label={t("p.admin.sla.fieldPriority")}
              fullWidth
              value={form.priority ?? 3}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  priority: Number(e.target.value) as TaskPriority,
                }))
              }
              helperText={t("p.admin.sla.priorityHelper")}
            >
              {Object.entries(PRIORITY_LABELS).map(([v, l]) => (
                <MenuItem key={v} value={v}>
                  {l}
                </MenuItem>
              ))}
            </TextField>
            <Stack direction="row" spacing={2}>
              <TextField
                label={t("p.admin.sla.fieldResponse")}
                type="number"
                fullWidth
                inputProps={{ min: 1 }}
                value={form.response_hours ?? 24}
                onChange={(e) =>
                  setForm((f) => ({ ...f, response_hours: Number(e.target.value) }))
                }
              />
              <TextField
                label={t("p.admin.sla.fieldResolution")}
                type="number"
                fullWidth
                inputProps={{ min: 1 }}
                value={form.resolution_hours ?? 72}
                onChange={(e) =>
                  setForm((f) => ({ ...f, resolution_hours: Number(e.target.value) }))
                }
              />
            </Stack>
            <FormControlLabel
              control={
                <Checkbox
                  checked={form.bump_priority ?? true}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, bump_priority: e.target.checked }))
                  }
                />
              }
              label={t("p.admin.sla.optBump")}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={form.notify_owner ?? true}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, notify_owner: e.target.checked }))
                  }
                />
              }
              label={t("p.admin.sla.optNotifyOwner")}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={form.notify_assignee ?? true}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, notify_assignee: e.target.checked }))
                  }
                />
              }
              label={t("p.admin.sla.optNotifyAssignee")}
            />
            <Tooltip title={t("p.admin.sla.resolutionTooltip")}>
              <Alert severity="info" variant="outlined" sx={{ py: 0 }}>
                {t("p.admin.sla.escalationNote")}
              </Alert>
            </Tooltip>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={!form.name || saveMut.isPending}
            onClick={() => saveMut.mutate(form)}
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
