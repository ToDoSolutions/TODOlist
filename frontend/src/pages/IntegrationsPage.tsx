import { formatDateTime } from "../lib/dates";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  chatIntegrationsApi,
  chatLogsApi,
  projectsApi,
  type ApiPayload,
} from "../api/resources";
import { inboundWebhooksApi, type InboundWebhookItem } from "../api/featPublic";
import { ssoApi } from "../api/featEnt";
import type { ChatIntegration, ChatMessageLog } from "../types";
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
  Chip,
  IconButton,
  Switch,
  FormControlLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Stack,
  useTheme,
  Grid,
  Card,
  CardContent,
  CardActions,
} from "@mui/material";
import {
  Trash2,
  Send,
  Pencil,
  MessageSquare,
  Webhook,
  Copy,
  Github,
  Calendar,
  Mail,
  Bell,
  ShieldCheck,
  KeyRound,
  Download,
  Puzzle,
  type LucideIcon,
} from "lucide-react";
import { Link as RouterLink } from "react-router-dom";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import PageHeader from "../components/ui/PageHeader";
import { ErrorState } from "../components/ui/states";
import { TaskListSkeleton } from "../components/ui/skeletons";
import { useTranslation } from "react-i18next";

export default function IntegrationsPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [open, setOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<ChatIntegration | null>(null);
  const [provider, setProvider] = useState("slack");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [events, setEvents] = useState("task_created,task_completed");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["chat-integrations"],
    queryFn: chatIntegrationsApi.list,
  });
  const integrations = data ?? [];

  const createMutation = useMutation({
    mutationFn: chatIntegrationsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-integrations"] });
      setOpen(false);
      setWebhookUrl("");
      notify.success(t("p.integr.chatCreated"));
    },
    onError: () => notify.error(t("p.integr.chatCreateError")),
  });

  const deleteMutation = useMutation({
    mutationFn: chatIntegrationsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-integrations"] });
      notify.success(t("p.integr.chatDeleted"));
    },
    onError: () => notify.error(t("p.integr.chatDeleteError")),
  });

  const testMutation = useMutation({
    mutationFn: chatIntegrationsApi.test,
    onSuccess: (res: Record<string, unknown>) => {
      if (res?.success) notify.success(t("p.integr.chatTestOk"));
      else notify.error(t("p.integr.chatTestFailed", { error: res?.error || "" }));
    },
    onError: () => notify.error(t("p.integr.chatTestError")),
  });

  const { data: logsData } = useQuery({
    queryKey: ["chat-logs"],
    queryFn: chatLogsApi.list,
  });
  const allLogs = logsData || [];

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiPayload }) =>
      chatIntegrationsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-integrations"] });
      notify.success(t("p.integr.chatUpdated"));
    },
    onError: () => notify.error(t("p.integr.chatUpdateError")),
  });

  // ===================== Webhooks entrantes =====================
  const [inboundOpen, setInboundOpen] = useState(false);
  const [inboundName, setInboundName] = useState("");
  const [inboundProject, setInboundProject] = useState<number | "">("");

  const { data: inboundData } = useQuery({
    queryKey: ["inbound-webhooks"],
    queryFn: inboundWebhooksApi.list,
  });
  const inbounds = Array.isArray(inboundData) ? inboundData : [];

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const inboundProjects = Array.isArray(projectsData) ? projectsData : [];
  const inboundProjectName = new Map(inboundProjects.map((p) => [p.id, p.name]));

  const inboundCreateMut = useMutation({
    mutationFn: (data: { name: string; project?: number | null }) =>
      inboundWebhooksApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inbound-webhooks"] });
      setInboundOpen(false);
      setInboundName("");
      setInboundProject("");
      notify.success(t("p.public.inbound.createdOk"));
    },
  });

  const inboundUpdateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<InboundWebhookItem> }) =>
      inboundWebhooksApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inbound-webhooks"] });
      notify.success(t("p.public.inbound.updatedOk"));
    },
  });

  const inboundDeleteMut = useMutation({
    mutationFn: (id: number) => inboundWebhooksApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inbound-webhooks"] });
      notify.success(t("p.public.inbound.deletedOk"));
    },
  });

  // Providers SSO (endpoint público): alimenta el estado OIDC del catálogo.
  // No fatal si el backend aún no lo expone.
  const { data: ssoProviders } = useQuery({
    queryKey: ["sso-providers"],
    queryFn: ssoApi.providers,
    retry: false,
  });

  const inboundUrl = (token: string) => `${window.location.origin}/api/inbound/${token}/`;

  const copyInboundUrl = (token: string) => {
    void navigator.clipboard.writeText(inboundUrl(token));
    notify.success(t("p.public.links.copied"));
  };

  // El catálogo es estático; el query solo alimenta la sección de chat.

  const openEdit = (int: ChatIntegration) => {
    setEditing(int);
    setProvider(int.provider || "slack");
    setWebhookUrl(int.webhook_url || "");
    setEvents(Array.isArray(int.events) ? int.events.join(", ") : "");
    setEditOpen(true);
  };

  const submitEdit = () => {
    if (!editing) return;
    updateMutation.mutate({
      id: editing.id,
      data: {
        provider,
        webhook_url: webhookUrl,
        events: events
          .split(",")
          .map((e) => e.trim())
          .filter(Boolean),
      },
    });
    setEditOpen(false);
    setEditing(null);
  };

  // ===================== Catálogo de integraciones =====================
  type CatalogStatus = "connected" | "available" | "unconfigured";

  // Estado calculado solo donde hay datos triviales en la página:
  // chat (lista de integraciones), webhooks entrantes (lista) y OIDC
  // (ssoApi.providers). El resto se muestra como "Disponible".
  const chatConnected = (integrations as ChatIntegration[]).some((i) => !!i.is_active);
  const inboundConnected = inbounds.length > 0;
  const oidcEnabled = !!ssoProviders?.find((p) => p.id === "oidc")?.enabled;

  const catalog: {
    key: string;
    icon: LucideIcon;
    to: string;
    status: CatalogStatus;
  }[] = [
    { key: "github", icon: Github, to: "/app/github", status: "available" },
    {
      key: "chat",
      icon: MessageSquare,
      to: "/app/integrations",
      status: chatConnected ? "connected" : "available",
    },
    {
      key: "inbound",
      icon: Webhook,
      to: "/app/integrations",
      status: inboundConnected ? "connected" : "available",
    },
    { key: "outbound", icon: Send, to: "/app/webhooks", status: "available" },
    { key: "ical", icon: Calendar, to: "/app/import-export", status: "available" },
    { key: "email", icon: Mail, to: "/app/profile", status: "available" },
    { key: "push", icon: Bell, to: "/app/profile", status: "available" },
    {
      key: "sso",
      icon: ShieldCheck,
      to: "/app/security",
      status: oidcEnabled ? "connected" : "unconfigured",
    },
    { key: "apiKeys", icon: KeyRound, to: "/app/api-keys", status: "available" },
    { key: "import", icon: Download, to: "/app/import-export", status: "available" },
  ];

  const statusChip = (s: CatalogStatus) =>
    s === "connected"
      ? { label: t("p.ent.market.status.connected"), color: "success" as const }
      : s === "unconfigured"
        ? {
            label: t("p.ent.market.status.unconfigured"),
            color: "warning" as const,
          }
        : { label: t("p.ent.market.status.available"), color: "default" as const };

  return (
    <Box>
      <PageHeader title={t("p.shell.integrations")} />

      {/* ===================== Catálogo ===================== */}
      <Box mb={4}>
        <Stack direction="row" alignItems="center" spacing={1} mb={0.5}>
          <Puzzle size={20} style={{ color: theme.palette.primary.main }} />
          <Typography variant="subtitle1" fontWeight={600}>
            {t("p.ent.market.title")}
          </Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary" mb={2}>
          {t("p.ent.market.desc")}
        </Typography>
        <Grid container spacing={2}>
          {catalog.map((c) => {
            const chip = statusChip(c.status);
            const Icon = c.icon;
            return (
              <Grid item xs={12} sm={6} md={4} key={c.key}>
                <Card
                  variant="outlined"
                  sx={{ height: "100%", display: "flex", flexDirection: "column" }}
                >
                  <CardContent sx={{ flex: 1 }}>
                    <Stack direction="row" spacing={1.5} alignItems="center" mb={1}>
                      <Icon size={20} style={{ color: theme.palette.primary.main }} />
                      <Typography variant="subtitle2" fontWeight={700} sx={{ flex: 1 }}>
                        {t(`p.ent.market.${c.key}.name`)}
                      </Typography>
                      <Chip
                        size="small"
                        label={chip.label}
                        color={chip.color}
                        variant={chip.color === "default" ? "outlined" : "filled"}
                      />
                    </Stack>
                    <Typography variant="body2" color="text.secondary">
                      {t(`p.ent.market.${c.key}.desc`)}
                    </Typography>
                  </CardContent>
                  <CardActions sx={{ px: 2, pb: 2, pt: 0 }}>
                    <Button size="small" component={RouterLink} to={c.to}>
                      {t("p.ent.market.configure")}
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      </Box>

      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 2,
        }}
      >
        <Typography variant="subtitle1" fontWeight={600}>
          {t("p.integr.chatTitle")}
        </Typography>
        <Button variant="contained" onClick={() => setOpen(true)}>
          {t("p.integr.chatNew")}
        </Button>
      </Box>

      {isLoading && <TaskListSkeleton rows={2} />}
      {isError && (
        <ErrorState
          title={t("p.integr.chatLoadError")}
          onRetry={() => void refetch()}
        />
      )}

      {integrations.map((int: ChatIntegration) => (
        <Paper key={int.id} sx={{ p: 2, mb: 2 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Chip label={int.provider} color="primary" size="small" />
            <Typography sx={{ flex: 1 }} variant="body2" noWrap>
              {int.webhook_url}
            </Typography>
            <FormControlLabel
              control={
                <Switch
                  checked={!!int.is_active}
                  size="small"
                  onChange={(e) =>
                    updateMutation.mutate({
                      id: int.id,
                      data: { is_active: e.target.checked },
                    })
                  }
                />
              }
              label={t("p.integr.chatActive")}
            />
            <IconButton onClick={() => openEdit(int)} title={t("p.integr.edit")}>
              <Pencil size={16} />
            </IconButton>
            <IconButton
              onClick={() => testMutation.mutate(int.id)}
              title={t("p.integr.test")}
            >
              <Send size={16} />
            </IconButton>
            <IconButton
              onClick={async () => {
                if (
                  await confirm(t("p.integr.chatConfirmDelete", { name: int.name }), {
                    confirmLabel: t("common.delete"),
                  })
                )
                  deleteMutation.mutate(int.id);
              }}
              title={t("p.integr.delete")}
            >
              <Trash2 size={16} />
            </IconButton>
          </Box>
          <Box sx={{ mt: 1, display: "flex", gap: 0.5, flexWrap: "wrap" }}>
            {(Array.isArray(int.events)
              ? int.events
              : (int.events || "").split(",").filter(Boolean)
            ).map((e: string) => (
              <Chip key={e} label={e.trim()} size="small" variant="outlined" />
            ))}
          </Box>
        </Paper>
      ))}

      <Dialog open={open} onClose={() => setOpen(false)}>
        <DialogTitle>{t("p.integr.chatNew")}</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            select
            label={t("p.integr.chatProvider")}
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            sx={{ mt: 1 }}
            SelectProps={{ native: true }}
          >
            <option value="slack">Slack</option>
            <option value="discord">Discord</option>
          </TextField>
          <TextField
            fullWidth
            label={t("p.integr.chatWebhookUrl")}
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
            sx={{ mt: 2 }}
          />
          <TextField
            fullWidth
            label={t("p.integr.chatEventsLabel")}
            value={events}
            onChange={(e) => setEvents(e.target.value)}
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>{t("p.integr.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() =>
              createMutation.mutate({
                provider,
                webhook_url: webhookUrl,
                events: events.split(",").map((e) => e.trim()),
              })
            }
            disabled={createMutation.isPending}
          >
            {t("p.integr.create")}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={editOpen}
        onClose={() => {
          setEditOpen(false);
          setEditing(null);
        }}
      >
        <DialogTitle>{t("p.integr.chatEditTitle")}</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            select
            label={t("p.integr.chatProvider")}
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            sx={{ mt: 1 }}
            SelectProps={{ native: true }}
          >
            <option value="slack">Slack</option>
            <option value="discord">Discord</option>
          </TextField>
          <TextField
            fullWidth
            label={t("p.integr.chatWebhookUrl")}
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
            sx={{ mt: 2 }}
          />
          <TextField
            fullWidth
            label={t("p.integr.chatEventsLabel")}
            value={events}
            onChange={(e) => setEvents(e.target.value)}
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setEditOpen(false);
              setEditing(null);
            }}
          >
            {t("p.integr.cancel")}
          </Button>
          <Button
            variant="contained"
            onClick={submitEdit}
            disabled={updateMutation.isPending}
          >
            {t("p.integr.save")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===================== Webhooks entrantes ===================== */}
      <Box mt={4}>
        <Stack direction="row" alignItems="center" spacing={1} mb={2}>
          <Webhook size={20} style={{ color: theme.palette.primary.main }} />
          <Typography variant="subtitle1" fontWeight={600}>
            {t("p.public.inbound.title")}
          </Typography>
          <Box flex={1} />
          <Button size="small" variant="contained" onClick={() => setInboundOpen(true)}>
            {t("p.public.inbound.new")}
          </Button>
        </Stack>
        <Typography variant="body2" color="text.secondary" mb={2}>
          {t("p.public.inbound.description")}
        </Typography>
        {inbounds.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
            <Typography color="text.secondary">{t("p.public.inbound.empty")}</Typography>
          </Paper>
        ) : (
          inbounds.map((wh) => {
            const postUrl = inboundUrl(wh.token);
            const curl = `curl -X POST ${postUrl} -H "Content-Type: application/json" -d '{"title":"Nueva tarea","description":"Opcional","priority":2,"due_date":"2026-01-31"}'`;
            return (
              <Paper key={wh.id} variant="outlined" sx={{ p: 2, mb: 2 }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  <Typography variant="body2" fontWeight={600} sx={{ flex: 1 }}>
                    {wh.name}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ fontFamily: "monospace" }}
                  >
                    {wh.token.slice(0, 8)}…
                  </Typography>
                  <Chip
                    size="small"
                    variant="outlined"
                    label={
                      wh.project != null
                        ? (inboundProjectName.get(wh.project) ?? `#${wh.project}`)
                        : t("p.public.inbound.inboxOption")
                    }
                  />
                  <Typography variant="caption" color="text.secondary">
                    {t("p.public.inbound.colLastUsed")}:{" "}
                    {wh.last_used_at
                      ? formatDateTime(wh.last_used_at)
                      : t("p.public.inbound.never")}
                  </Typography>
                  <FormControlLabel
                    control={
                      <Switch
                        size="small"
                        checked={!!wh.is_active}
                        onChange={(e) =>
                          inboundUpdateMut.mutate({
                            id: wh.id,
                            data: { is_active: e.target.checked },
                          })
                        }
                      />
                    }
                    label={t("p.public.inbound.active")}
                  />
                  <IconButton
                    size="small"
                    onClick={() => copyInboundUrl(wh.token)}
                    title={t("p.public.inbound.copyUrl")}
                  >
                    <Copy size={15} />
                  </IconButton>
                  <IconButton
                    size="small"
                    onClick={async () => {
                      if (
                        await confirm(
                          t("p.public.inbound.confirmDelete", { name: wh.name }),
                          { confirmLabel: t("common.delete") },
                        )
                      )
                        inboundDeleteMut.mutate(wh.id);
                    }}
                    title={t("p.integr.delete")}
                  >
                    <Trash2 size={15} />
                  </IconButton>
                </Box>
                <TextField
                  size="small"
                  fullWidth
                  label={t("p.public.inbound.postUrlLabel")}
                  value={postUrl}
                  InputProps={{ readOnly: true }}
                  onFocus={(e) => e.target.select()}
                  sx={{ mt: 1.5 }}
                />
                <Typography
                  component="pre"
                  variant="caption"
                  color="text.secondary"
                  sx={{
                    mt: 1,
                    p: 1,
                    borderRadius: 1,
                    bgcolor: "action.hover",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-all",
                    fontFamily: "monospace",
                  }}
                >
                  {curl}
                </Typography>
              </Paper>
            );
          })
        )}

        <Dialog open={inboundOpen} onClose={() => setInboundOpen(false)}>
          <DialogTitle>{t("p.public.inbound.createTitle")}</DialogTitle>
          <DialogContent>
            <TextField
              fullWidth
              required
              label={t("p.public.inbound.nameLabel")}
              value={inboundName}
              onChange={(e) => setInboundName(e.target.value)}
              sx={{ mt: 1 }}
            />
            <TextField
              fullWidth
              select
              label={t("p.public.inbound.projectLabel")}
              value={inboundProject}
              onChange={(e) =>
                setInboundProject(e.target.value === "" ? "" : Number(e.target.value))
              }
              sx={{ mt: 2 }}
              SelectProps={{ native: true }}
            >
              <option value="">{t("p.public.inbound.inboxOption")}</option>
              {inboundProjects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </TextField>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setInboundOpen(false)}>{t("p.integr.cancel")}</Button>
            <Button
              variant="contained"
              disabled={!inboundName.trim() || inboundCreateMut.isPending}
              onClick={() =>
                inboundCreateMut.mutate({
                  name: inboundName.trim(),
                  project: inboundProject === "" ? null : inboundProject,
                })
              }
            >
              {t("p.integr.create")}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>

      {/* ===================== Chat message logs ===================== */}
      <Box mt={4}>
        <Stack direction="row" alignItems="center" spacing={1} mb={2}>
          <MessageSquare size={20} style={{ color: theme.palette.primary.main }} />
          <Typography variant="subtitle1" fontWeight={600}>
            {t("p.integr.chatLogTitle")}
          </Typography>
        </Stack>
        {allLogs.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
            <Typography color="text.secondary">{t("p.integr.chatLogEmpty")}</Typography>
          </Paper>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t("p.integr.chatColIntegration")}</TableCell>
                  <TableCell>{t("p.integr.event")}</TableCell>
                  <TableCell>{t("p.integr.status")}</TableCell>
                  <TableCell>{t("p.integr.chatColCode")}</TableCell>
                  <TableCell>{t("p.integr.date")}</TableCell>
                  <TableCell>{t("p.integr.error")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {allLogs.map((log: ChatMessageLog) => (
                  <TableRow key={log.id}>
                    <TableCell>
                      <Typography variant="body2">#{log.integration}</Typography>
                    </TableCell>
                    <TableCell>
                      <Chip size="small" label={log.event} variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={log.success ? t("p.integr.ok") : t("p.integr.failed")}
                        sx={{
                          height: 18,
                          fontSize: 10,
                          bgcolor: log.success ? "success.main" : "error.main",
                          color: "common.white",
                        }}
                      />
                    </TableCell>
                    <TableCell>{log.status_code || "—"}</TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {log.created_at ? formatDateTime(log.created_at) : "—"}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography
                        variant="body2"
                        color="error.main"
                        noWrap
                        sx={{ maxWidth: 200 }}
                      >
                        {log.error || "—"}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>
    </Box>
  );
}
