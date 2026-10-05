import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Typography,
  Stack,
  Paper,
  Button,
  TextField,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Switch,
  Tooltip,
  CircularProgress,
} from "@mui/material";
import { Plus, Trash2, RefreshCw, CalendarPlus, AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { formatDateTime } from "../lib/dates";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/states";
import { externalCalendarsApi, type ExternalCalendar } from "../api/featExtras";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import "../i18n";

/**
 * Calendarios externos: suscripciones iCal cuyos eventos se superponen
 * en la vista de calendario de tareas (CalendarView).
 */
export default function ExternalCalendarsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [dialog, setDialog] = useState(false);
  const [form, setForm] = useState({ name: "", url: "", color: "#607d8b" });

  const { data: calendars = [] } = useQuery({
    queryKey: ["external-calendars"],
    queryFn: externalCalendarsApi.list,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["external-calendars"] });

  const createMut = useMutation({
    mutationFn: () =>
      externalCalendarsApi.create({
        name: form.name.trim(),
        url: form.url.trim(),
        color: form.color,
      }),
    onSuccess: () => {
      invalidate();
      setDialog(false);
      setForm({ name: "", url: "", color: "#607d8b" });
      notify.success(t("p.extras.cal.created"));
    },
    onError: () => notify.error(t("p.extras.cal.createError")),
  });

  const toggleMut = useMutation({
    mutationFn: (cal: ExternalCalendar) =>
      externalCalendarsApi.update(cal.id, { is_active: !cal.is_active }),
    onSuccess: invalidate,
    onError: () => notify.error(t("p.extras.cal.updateError")),
  });

  const refreshMut = useMutation({
    mutationFn: (id: number) => externalCalendarsApi.refresh(id),
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ["external-calendar-events"] });
      notify.success(t("p.extras.cal.refreshed"));
    },
    onError: () => notify.error(t("p.extras.cal.refreshError")),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => externalCalendarsApi.remove(id),
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ["external-calendar-events"] });
      notify.success(t("p.extras.cal.deleted"));
    },
    onError: () => notify.error(t("p.extras.cal.deleteError")),
  });

  return (
    <Box>
      <PageHeader
        title={t("p.extras.cal.title")}
        description={t("p.extras.cal.desc")}
        breadcrumbs={[
          { label: t("nav.projects") },
          { label: t("p.extras.cal.title") },
        ]}
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={15} />}
            onClick={() => setDialog(true)}
          >
            {t("p.extras.cal.new")}
          </Button>
        }
      />

      {calendars.length === 0 ? (
        <EmptyState
          title={t("p.extras.cal.emptyTitle")}
          description={t("p.extras.cal.emptyDesc")}
          icon={<CalendarPlus size={48} strokeWidth={1.2} />}
          action={
            <Button
              variant="outlined"
              startIcon={<Plus size={15} />}
              onClick={() => setDialog(true)}
            >
              {t("p.extras.cal.new")}
            </Button>
          }
        />
      ) : (
        <Stack spacing={1}>
          {calendars.map((cal) => (
            <Paper key={cal.id} variant="outlined" sx={{ p: 1.5 }}>
              <Stack direction="row" alignItems="center" spacing={1.5}>
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: "50%",
                    bgcolor: cal.color || "#607d8b",
                    flexShrink: 0,
                  }}
                />
                <Box flex={1} minWidth={0}>
                  <Typography variant="body2" fontWeight={600} noWrap>
                    {cal.name}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    noWrap
                    display="block"
                    title={cal.url}
                  >
                    {cal.url}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {t("p.extras.cal.lastSynced")}:{" "}
                    {cal.last_synced_at
                      ? formatDateTime(cal.last_synced_at)
                      : t("p.extras.cal.neverSynced")}
                  </Typography>
                  {cal.last_error && (
                    <Stack
                      direction="row"
                      spacing={0.5}
                      alignItems="center"
                      sx={{ mt: 0.25, color: "error.main" }}
                    >
                      <AlertTriangle size={12} />
                      <Typography variant="caption" title={cal.last_error}>
                        {t("p.extras.cal.syncError")}: {cal.last_error}
                      </Typography>
                    </Stack>
                  )}
                </Box>
                <Switch
                  size="small"
                  checked={cal.is_active}
                  onChange={() => toggleMut.mutate(cal)}
                  inputProps={{ "aria-label": t("p.extras.cal.active") }}
                />
                <Tooltip title={t("p.extras.cal.refresh")}>
                  <span>
                    <IconButton
                      size="small"
                      aria-label={t("p.extras.cal.refreshAria")}
                      disabled={refreshMut.isPending && refreshMut.variables === cal.id}
                      onClick={() => refreshMut.mutate(cal.id)}
                    >
                      {refreshMut.isPending && refreshMut.variables === cal.id ? (
                        <CircularProgress size={16} />
                      ) : (
                        <RefreshCw size={16} />
                      )}
                    </IconButton>
                  </span>
                </Tooltip>
                <IconButton
                  size="small"
                  color="error"
                  aria-label={t("p.extras.cal.deleteAria")}
                  onClick={async () => {
                    if (
                                await confirm(t("p.extras.cal.confirmDelete"), {
                                  confirmLabel: t("common.delete"),
                                })
                              )
                      deleteMut.mutate(cal.id);
                  }}
                >
                  <Trash2 size={16} />
                </IconButton>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      {/* Nuevo calendario */}
      <Dialog open={dialog} onClose={() => setDialog(false)} fullWidth maxWidth="xs">
        <DialogTitle>{t("p.extras.cal.new")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField
              label={t("p.extras.cal.name")}
              fullWidth
              autoFocus
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <TextField
              label={t("p.extras.cal.url")}
              fullWidth
              type="url"
              placeholder="https://…/calendar.ics"
              helperText={t("p.extras.cal.urlHint")}
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
            />
            <Stack direction="row" spacing={2} alignItems="center">
              <TextField
                label={t("common.color")}
                type="color"
                value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
                sx={{ width: 80 }}
                InputLabelProps={{ shrink: true }}
              />
              <Chip
                label={form.name || t("p.extras.cal.name")}
                sx={{ bgcolor: form.color, color: "common.white" }}
              />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={!form.name.trim() || !form.url.trim() || createMut.isPending}
            onClick={() => createMut.mutate()}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
