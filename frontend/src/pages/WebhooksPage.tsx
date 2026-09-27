import { formatDateTime } from "../lib/dates";
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
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Chip,
  Switch,
  FormControlLabel,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Tabs,
  Tab,
  useTheme,
} from "@mui/material";
import {
  Plus,
  Pencil,
  Trash2,
  Send,
  Webhook,
  ArrowDownToLine,
  ArrowUpFromLine,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { outgoingWebhooksApi, type ApiPayload } from "../api/resources";
import type { OutgoingWebhook, WebhookDelivery } from "../types";
import { notify } from "../notify";
import { useTranslation } from "react-i18next";

interface WebhookForm {
  url: string;
  events: string;
  secret: string;
  is_active: boolean;
}

const EMPTY_FORM: WebhookForm = { url: "", events: "", secret: "", is_active: true };

export default function WebhooksPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();
  const [tab, setTab] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [form, setForm] = useState<WebhookForm>(EMPTY_FORM);
  const [testResult, setTestResult] = useState<string | null>(null);

  const { data: webhooks, isLoading } = useQuery({
    queryKey: ["outgoing-webhooks"],
    queryFn: outgoingWebhooksApi.list,
  });

  const { data: deliveries } = useQuery({
    queryKey: ["webhook-deliveries"],
    queryFn: outgoingWebhooksApi.deliveries,
  });

  const createMut = useMutation({
    mutationFn: outgoingWebhooksApi.create,
    onSuccess: () => {
      notify.success(t("p.integr.whCreated"));
      qc.invalidateQueries({ queryKey: ["outgoing-webhooks"] });
      setDialogOpen(false);
    },
    onError: () => notify.error(t("p.integr.whCreateError")),
  });

  const updateMut = useMutation({
    mutationFn: (data: { id: number; payload: ApiPayload }) =>
      outgoingWebhooksApi.update(data.id, data.payload),
    onSuccess: () => {
      notify.success(t("p.integr.whUpdated"));
      qc.invalidateQueries({ queryKey: ["outgoing-webhooks"] });
      setDialogOpen(false);
    },
    onError: () => notify.error(t("p.integr.whUpdateError")),
  });

  const deleteMut = useMutation({
    mutationFn: outgoingWebhooksApi.delete,
    onSuccess: () => {
      notify.info(t("p.integr.whDeleted"));
      qc.invalidateQueries({ queryKey: ["outgoing-webhooks"] });
      setDeleteId(null);
    },
    onError: () => notify.error(t("p.integr.whDeleteError")),
  });

  const testMut = useMutation({
    mutationFn: outgoingWebhooksApi.test,
    onSuccess: (data: Record<string, unknown>) => {
      notify.success(t("p.integr.whTestSent"));
      setTestResult(JSON.stringify(data, null, 2));
    },
    onError: () => notify.error(t("p.integr.whTestError")),
  });

  const toggleMut = useMutation({
    mutationFn: (data: { id: number; is_active: boolean }) =>
      outgoingWebhooksApi.update(data.id, { is_active: data.is_active }),
    onSuccess: () => {
      notify.info(t("p.integr.whStateUpdated"));
      qc.invalidateQueries({ queryKey: ["outgoing-webhooks"] });
    },
    onError: () => notify.error(t("p.integr.whStateError")),
  });

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setDialogOpen(true);
  };

  const openEdit = (w: OutgoingWebhook) => {
    setForm({
      url: w.url || "",
      events: Array.isArray(w.events) ? w.events.join(", ") : w.events || "",
      secret: w.secret || "",
      is_active: w.is_active ?? true,
    });
    setEditingId(w.id);
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    const payload: ApiPayload = {
      url: form.url,
      events: form.events
        .split(",")
        .map((e) => e.trim())
        .filter(Boolean),
      is_active: form.is_active,
    };
    if (form.secret) payload.secret = form.secret;
    if (editingId) {
      updateMut.mutate({ id: editingId, payload });
    } else {
      createMut.mutate(payload);
    }
  };

  const webhookList: OutgoingWebhook[] = Array.isArray(webhooks)
    ? webhooks
    : (webhooks as { results?: OutgoingWebhook[] })?.results || [];
  const allDeliveries: WebhookDelivery[] = Array.isArray(deliveries)
    ? deliveries
    : (deliveries as { results?: WebhookDelivery[] } | undefined)?.results || [];
  // Separar entregas: las que tienen repo_full_name son entrantes (GitHub), el resto salientes
  const incomingDeliveries = allDeliveries.filter(
    (d) => d.repo_full_name || d.event_type?.includes("."),
  );
  const outgoingDeliveries = allDeliveries.filter(
    (d) => !d.repo_full_name && !d.event_type?.includes("."),
  );

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={3}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Webhook size={24} style={{ color: theme.palette.primary.main }} />
          <Typography variant="h5" fontWeight={700}>
            {t("p.integr.whTitle")}
          </Typography>
        </Stack>
      </Stack>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
        <Tab
          icon={<ArrowUpFromLine size={16} />}
          iconPosition="start"
          label={t("p.integr.whOutgoing")}
        />
        <Tab
          icon={<ArrowDownToLine size={16} />}
          iconPosition="start"
          label={t("p.integr.whIncoming")}
        />
      </Tabs>

      {tab === 0 && (
        <>
          <Stack
            direction="row"
            alignItems="center"
            justifyContent="space-between"
            mb={2}
          >
            <Typography variant="subtitle1" fontWeight={600}>
              {t("p.integr.whOutgoingTitle")}
            </Typography>
            <Button
              variant="contained"
              startIcon={<Plus size={18} />}
              onClick={openCreate}
            >
              {t("p.integr.whNew")}
            </Button>
          </Stack>

          {isLoading ? (
            <Box display="flex" justifyContent="center" py={5}>
              <CircularProgress />
            </Box>
          ) : webhookList.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
              <Send size={48} color="text.disabled" />
              <Typography color="text.secondary" mt={1}>
                {t("p.integr.whEmpty")}
              </Typography>
            </Paper>
          ) : (
            <Stack spacing={2}>
              {webhookList.map((w) => (
                <Paper key={w.id} variant="outlined" sx={{ p: 2 }}>
                  <Stack
                    direction="row"
                    alignItems="flex-start"
                    justifyContent="space-between"
                  >
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography
                        variant="subtitle1"
                        fontWeight={600}
                        fontFamily="monospace"
                        noWrap
                      >
                        {w.url}
                      </Typography>
                      <Stack
                        direction="row"
                        spacing={0.5}
                        mt={1}
                        flexWrap="wrap"
                        useFlexGap
                      >
                        {(Array.isArray(w.events)
                          ? w.events
                          : (w.events || "").split(",").filter(Boolean)
                        ).map((e: string) => (
                          <Chip
                            key={e}
                            size="small"
                            label={e}
                            sx={{ height: 20, fontSize: 10 }}
                            variant="outlined"
                          />
                        ))}
                      </Stack>
                      <Stack direction="row" spacing={2} mt={1} alignItems="center">
                        <Chip
                          size="small"
                          label={
                            w.is_active ? t("p.integr.active") : t("p.integr.inactive")
                          }
                          sx={{
                            height: 20,
                            fontSize: 10,
                            bgcolor: w.is_active ? "success.main" : "grey.400",
                            color: "common.white",
                          }}
                        />
                        <Typography variant="caption" color="text.secondary">
                          {t("p.integr.whLastFired", {
                            date: w.last_triggered
                              ? formatDateTime(w.last_triggered)
                              : t("p.integr.never"),
                          })}
                        </Typography>
                      </Stack>
                    </Box>
                    <Stack direction="row" spacing={0.5} alignItems="center">
                      <FormControlLabel
                        control={
                          <Switch
                            size="small"
                            checked={!!w.is_active}
                            onChange={(e) =>
                              toggleMut.mutate({ id: w.id, is_active: e.target.checked })
                            }
                          />
                        }
                        label=""
                      />
                      <Tooltip title={t("p.integr.test")}>
                        <IconButton
                          size="small"
                          color="primary"
                          onClick={() => {
                            setTestResult(null);
                            testMut.mutate(w.id);
                          }}
                        >
                          <Send size={16} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title={t("p.integr.edit")}>
                        <IconButton size="small" onClick={() => openEdit(w)}>
                          <Pencil size={16} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title={t("p.integr.delete")}>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => setDeleteId(w.id)}
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

          {testResult && (
            <Paper
              variant="outlined"
              sx={{
                p: 2,
                mt: 2,
                fontFamily: "monospace",
                whiteSpace: "pre-wrap",
                bgcolor: "action.hover",
              }}
            >
              <Typography variant="caption" color="text.secondary" mb={1} display="block">
                {t("p.integr.testResult")}
              </Typography>
              {testResult}
            </Paper>
          )}

          {/* Historial de entregas salientes */}
          <Box mt={4}>
            <Typography variant="h6" fontWeight={700} mb={2}>
              {t("p.integr.whOutgoingHistory")}
            </Typography>
            {outgoingDeliveries.length === 0 ? (
              <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
                <Typography color="text.secondary">
                  {t("p.integr.whOutgoingEmpty")}
                </Typography>
              </Paper>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t("p.integr.event")}</TableCell>
                    <TableCell>{t("p.integr.action")}</TableCell>
                    <TableCell>{t("p.integr.status")}</TableCell>
                    <TableCell>{t("p.integr.error")}</TableCell>
                    <TableCell>{t("p.integr.date")}</TableCell>
                    <TableCell>{t("p.integr.retries")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {outgoingDeliveries.map((d) => {
                    const statusColors: Record<string, string> = {
                      success: "success.main",
                      failed: "error.main",
                      retrying: "warning.main",
                      pending: "info.main",
                    };
                    return (
                      <TableRow key={d.id}>
                        <TableCell>{d.event_type || "—"}</TableCell>
                        <TableCell>{d.action || "—"}</TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            label={d.status || "—"}
                            sx={{
                              height: 20,
                              fontSize: 10,
                              color: "common.white",
                              bgcolor: statusColors[d.status || "pending"] || "grey.400",
                            }}
                          />
                        </TableCell>
                        <TableCell sx={{ maxWidth: 200 }}>
                          {d.error_message ? (
                            <Typography
                              variant="caption"
                              color="error.main"
                              noWrap
                              title={d.error_message}
                            >
                              {d.error_message}
                            </Typography>
                          ) : (
                            "—"
                          )}
                        </TableCell>
                        <TableCell>
                          {d.created_at ? formatDateTime(d.created_at) : "—"}
                        </TableCell>
                        <TableCell>
                          {d.retry_count ?? 0}/{d.max_retries ?? 0}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </Box>
        </>
      )}

      {tab === 1 && (
        <Box>
          <Typography variant="subtitle1" fontWeight={600} mb={2}>
            {t("p.integr.whIncomingTitle")}
          </Typography>
          <Alert severity="info" sx={{ mb: 2 }}>
            {t("p.integr.whIncomingInfo")}
          </Alert>
          {incomingDeliveries.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
              <Typography color="text.secondary">
                {t("p.integr.whIncomingEmpty")}
              </Typography>
            </Paper>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t("p.integr.event")}</TableCell>
                  <TableCell>{t("p.integr.action")}</TableCell>
                  <TableCell>{t("p.integr.status")}</TableCell>
                  <TableCell>{t("p.integr.repo")}</TableCell>
                  <TableCell>{t("p.integr.error")}</TableCell>
                  <TableCell>{t("p.integr.date")}</TableCell>
                  <TableCell>{t("p.integr.retries")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {incomingDeliveries.map((d) => {
                  const statusColors: Record<string, string> = {
                    success: "success.main",
                    failed: "error.main",
                    retrying: "warning.main",
                    pending: "info.main",
                  };
                  return (
                    <TableRow key={d.id}>
                      <TableCell>{d.event_type || "—"}</TableCell>
                      <TableCell>{d.action || "—"}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={d.status || "—"}
                          sx={{
                            height: 20,
                            fontSize: 10,
                            color: "common.white",
                            bgcolor: statusColors[d.status || "pending"] || "grey.400",
                          }}
                        />
                      </TableCell>
                      <TableCell>{d.repo_full_name || "—"}</TableCell>
                      <TableCell sx={{ maxWidth: 200 }}>
                        {d.error_message ? (
                          <Typography
                            variant="caption"
                            color="error.main"
                            noWrap
                            title={d.error_message}
                          >
                            {d.error_message}
                          </Typography>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell>
                        {d.created_at ? formatDateTime(d.created_at) : "—"}
                      </TableCell>
                      <TableCell>
                        {d.retry_count ?? 0}/{d.max_retries ?? 0}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </Box>
      )}

      {/* Dialog de creación/edición */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {editingId ? t("p.integr.whEditTitle") : t("p.integr.whCreateTitle")}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("p.integr.url")}
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
              fullWidth
              size="small"
              placeholder="https://example.com/webhook"
            />
            <TextField
              label={t("p.integr.whEventsLabel")}
              value={form.events}
              onChange={(e) => setForm({ ...form, events: e.target.value })}
              fullWidth
              size="small"
              helperText={t("p.integr.whEventsHelp")}
            />
            <TextField
              label={t("p.integr.whSecret")}
              value={form.secret}
              onChange={(e) => setForm({ ...form, secret: e.target.value })}
              fullWidth
              size="small"
              type="password"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
              }
              label={t("p.integr.active")}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>{t("p.integr.cancel")}</Button>
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={!form.url || createMut.isPending || updateMut.isPending}
          >
            {editingId ? t("p.integr.save") : t("p.integr.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog de confirmación de borrado */}
      <Dialog
        open={deleteId !== null}
        onClose={() => setDeleteId(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>{t("p.integr.whDeleteTitle")}</DialogTitle>
        <DialogContent>
          <Alert severity="warning">{t("p.integr.whDeleteConfirm")}</Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteId(null)}>{t("p.integr.cancel")}</Button>
          <Button
            variant="contained"
            color="error"
            onClick={() => deleteId && deleteMut.mutate(deleteId)}
            disabled={deleteMut.isPending}
          >
            {t("p.integr.delete")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
