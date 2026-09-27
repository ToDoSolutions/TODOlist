import { formatDateTime } from "../lib/dates";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notificationsApi, type ApiPayload } from "../api/resources";
import { taskX2Api, minutesUntilNextNineAM } from "../api/featTask2";
import { approvalsApi } from "../api/featTask3";
import type { AppNotification, NotificationPreference } from "../types";
import { notify } from "../notify";
import { TaskListSkeleton } from "../components/ui/skeletons";
import { EmptyState } from "../components/ui/states";
import {
  Box,
  Typography,
  Paper,
  Button,
  Stack,
  IconButton,
  Tooltip,
  Alert,
  Switch,
  FormControlLabel,
  TextField,
  Chip,
  Tabs,
  Tab,
  Divider,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
} from "@mui/material";
import {
  Bell,
  CheckCheck,
  Mail,
  MailPlus,
  BellOff,
  Settings,
  AlarmClock,
  Clock,
  CalendarClock,
  Check,
  X,
} from "lucide-react";

// El serializer de Notification expone `task` (FK) que aún no está en
// AppNotification de types.ts — se modela localmente como en featTask.
type NotificationX = AppNotification & { task?: number | null };

const isReminderNotif = (n: NotificationX): n is NotificationX & { task: number } =>
  n.type === "reminder" && typeof n.task === "number";

// Solicitud de aprobación pendiente: el payload lleva el id de la tarea
// en `task` (mismo campo que los recordatorios).
const isApprovalRequestNotif = (
  n: NotificationX,
): n is NotificationX & { task: number } =>
  n.type === "approval_request" && typeof n.task === "number";

export default function NotificationsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [tab, setTab] = useState(0);

  const { data: notifData, isLoading: notifLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: notificationsApi.list,
  });
  const notifications = notifData?.results || notifData || [];

  const { data: prefData, isLoading: prefLoading } = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: notificationsApi.preferences,
  });
  const preferences = prefData?.results || prefData || [];

  const markAllRead = useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => {
      notify.success(t("p.misc.notifications.markedAllRead"));
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["unread-count"] });
    },
  });

  const markRead = useMutation({
    mutationFn: (id: number) => notificationsApi.markRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["unread-count"] });
    },
  });

  const markUnread = useMutation({
    mutationFn: (id: number) => notificationsApi.markUnread(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const updatePref = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiPayload }) =>
      notificationsApi.updatePreference(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notification-preferences"] });
      notify.success(t("p.misc.notifications.prefUpdated"));
    },
    onError: () => notify.error(t("p.misc.notifications.prefUpdateError")),
  });

  // Posponer recordatorio: el menú ancla sobre la notificación y guarda
  // el taskId; las opciones calculan los minutos para snooze_reminder.
  const [snoozeAnchor, setSnoozeAnchor] = useState<{
    el: HTMLElement;
    taskId: number;
  } | null>(null);

  const snooze = useMutation({
    mutationFn: ({ taskId, minutes }: { taskId: number; minutes: number }) =>
      taskX2Api.snoozeReminder(taskId, minutes),
    onSuccess: (data) => {
      notify.success(
        data?.reminder_at
          ? t("p.taskx.snooze.until", { time: formatDateTime(data.reminder_at) })
          : t("p.taskx.snooze.done"),
      );
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["unread-count"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: () => notify.error(t("p.taskx.snooze.error")),
  });

  // Aprobar/rechazar en línea desde la notificación approval_request.
  const decideApproval = useMutation({
    mutationFn: ({
      taskId,
      decision,
    }: {
      taskId: number;
      decision: "approve" | "reject";
    }) =>
      decision === "approve" ? approvalsApi.approve(taskId) : approvalsApi.reject(taskId),
    onSuccess: (_d, v) => {
      notify.success(
        t(
          v.decision === "approve"
            ? "p.taskx.approval.approved"
            : "p.taskx.approval.rejected",
        ),
      );
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["unread-count"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: () => notify.error(t("p.taskx.approval.error")),
  });

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} mb={3}>
        {t("nav.notifications")}
      </Typography>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
        <Tab
          icon={<Bell size={16} />}
          iconPosition="start"
          label={t("p.misc.notifications.history")}
        />
        <Tab
          icon={<Settings size={16} />}
          iconPosition="start"
          label={t("p.misc.notifications.preferences")}
        />
      </Tabs>

      {/* Tab 1: Historial */}
      {tab === 0 && (
        <Box>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            mb={2}
          >
            <Typography variant="body2" color="text.secondary">
              {t("p.misc.notifications.count", { count: notifications.length })}
            </Typography>
            <Button
              size="small"
              startIcon={<CheckCheck size={16} />}
              onClick={() => markAllRead.mutate()}
              disabled={markAllRead.isPending}
            >
              {t("p.misc.notifications.markAllRead")}
            </Button>
          </Stack>

          {notifLoading ? (
            <TaskListSkeleton rows={6} />
          ) : notifications.length === 0 ? (
            <EmptyState
              icon={<BellOff size={48} strokeWidth={1.2} />}
              title={t("p.misc.notifications.empty")}
            />
          ) : (
            <Stack spacing={1}>
              {notifications.map((n: NotificationX) => (
                <Paper
                  key={n.id}
                  variant="outlined"
                  sx={{
                    p: 2,
                    bgcolor: n.read ? "transparent" : "action.hover",
                    borderLeft: n.read ? undefined : "3px solid",
                    borderColor: n.read ? undefined : "primary.main",
                  }}
                >
                  <Stack direction="row" spacing={2} alignItems="flex-start">
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="subtitle2" fontWeight={n.read ? 400 : 600}>
                        {n.title}
                      </Typography>
                      {n.body && (
                        <Typography variant="body2" color="text.secondary">
                          {n.body}
                        </Typography>
                      )}
                      <Stack direction="row" spacing={1} mt={0.5} alignItems="center">
                        <Chip
                          size="small"
                          label={
                            n.type
                              ? t(`p.misc.notifications.type.${n.type}`, {
                                  defaultValue: n.type.replace(/_/g, " "),
                                })
                              : undefined
                          }
                          sx={{ height: 20, fontSize: 10 }}
                        />
                        <Typography variant="caption" color="text.secondary">
                          {n.created_at && formatDateTime(n.created_at)}
                        </Typography>
                      </Stack>
                    </Box>
                    <Stack direction="row" spacing={0.5} alignItems="center">
                      {isApprovalRequestNotif(n) && (
                        <>
                          <Button
                            size="small"
                            variant="contained"
                            color="success"
                            startIcon={<Check size={14} />}
                            onClick={() =>
                              decideApproval.mutate({
                                taskId: n.task,
                                decision: "approve",
                              })
                            }
                            disabled={decideApproval.isPending}
                            sx={{ textTransform: "none", fontSize: 12 }}
                          >
                            {t("p.taskx.approval.approve")}
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            color="error"
                            startIcon={<X size={14} />}
                            onClick={() =>
                              decideApproval.mutate({
                                taskId: n.task,
                                decision: "reject",
                              })
                            }
                            disabled={decideApproval.isPending}
                            sx={{ textTransform: "none", fontSize: 12 }}
                          >
                            {t("p.taskx.approval.reject")}
                          </Button>
                        </>
                      )}
                      {isReminderNotif(n) && (
                        <Tooltip title={t("p.taskx.snooze.action")}>
                          <Button
                            size="small"
                            startIcon={<AlarmClock size={14} />}
                            onClick={(e) =>
                              setSnoozeAnchor({ el: e.currentTarget, taskId: n.task })
                            }
                            disabled={snooze.isPending}
                            sx={{ textTransform: "none", fontSize: 12 }}
                          >
                            {t("p.taskx.snooze.action")}
                          </Button>
                        </Tooltip>
                      )}
                      {n.read ? (
                        <Tooltip title={t("p.misc.notifications.markUnread")}>
                          <IconButton
                            size="small"
                            onClick={() => markUnread.mutate(n.id)}
                          >
                            <BellOff size={16} />
                          </IconButton>
                        </Tooltip>
                      ) : (
                        <Tooltip title={t("p.misc.notifications.markRead")}>
                          <IconButton size="small" onClick={() => markRead.mutate(n.id)}>
                            <CheckCheck size={16} />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Stack>
                  </Stack>
                </Paper>
              ))}
            </Stack>
          )}
          {/* Menú de posponer: compartido por todas las notificaciones
              de tipo reminder (la fila guarda el taskId en el ancla). */}
          <Menu
            anchorEl={snoozeAnchor?.el}
            open={!!snoozeAnchor}
            onClose={() => setSnoozeAnchor(null)}
          >
            <MenuItem
              onClick={() => {
                if (snoozeAnchor)
                  snooze.mutate({ taskId: snoozeAnchor.taskId, minutes: 15 });
                setSnoozeAnchor(null);
              }}
            >
              <ListItemIcon>
                <Clock size={16} />
              </ListItemIcon>
              <ListItemText>{t("p.taskx.snooze.15m")}</ListItemText>
            </MenuItem>
            <MenuItem
              onClick={() => {
                if (snoozeAnchor)
                  snooze.mutate({ taskId: snoozeAnchor.taskId, minutes: 60 });
                setSnoozeAnchor(null);
              }}
            >
              <ListItemIcon>
                <Clock size={16} />
              </ListItemIcon>
              <ListItemText>{t("p.taskx.snooze.1h")}</ListItemText>
            </MenuItem>
            <MenuItem
              onClick={() => {
                if (snoozeAnchor)
                  snooze.mutate({
                    taskId: snoozeAnchor.taskId,
                    minutes: minutesUntilNextNineAM(),
                  });
                setSnoozeAnchor(null);
              }}
            >
              <ListItemIcon>
                <CalendarClock size={16} />
              </ListItemIcon>
              <ListItemText>{t("p.taskx.snooze.tomorrow9")}</ListItemText>
            </MenuItem>
          </Menu>
        </Box>
      )}

      {/* Tab 2: Preferencias */}
      {tab === 1 && (
        <Box>
          <Typography variant="body2" color="text.secondary" mb={2}>
            {t("p.misc.notifications.prefsDesc")}
          </Typography>
          {prefLoading ? (
            <TaskListSkeleton rows={3} />
          ) : preferences.length === 0 ? (
            <Alert severity="info">{t("p.misc.notifications.noPrefs")}</Alert>
          ) : (
            <Stack spacing={1}>
              {preferences.map((pref: NotificationPreference) => (
                <Paper key={pref.id} variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="subtitle2" fontWeight={600} mb={1}>
                    {pref.notification_type
                      ? t(`p.misc.notifications.type.${pref.notification_type}`, {
                          defaultValue: pref.notification_type.replace(/_/g, " "),
                        })
                      : ""}
                  </Typography>
                  <Divider sx={{ mb: 1 }} />
                  <Stack direction="row" spacing={3}>
                    <FormControlLabel
                      control={
                        <Switch
                          size="small"
                          checked={!!pref.in_app_enabled}
                          onChange={(e) =>
                            updatePref.mutate({
                              id: pref.id,
                              data: { in_app_enabled: e.target.checked },
                            })
                          }
                        />
                      }
                      label={
                        <Stack direction="row" spacing={1} alignItems="center">
                          <Bell size={16} />
                          <Typography variant="body2">
                            {t("p.misc.notifications.inApp")}
                          </Typography>
                        </Stack>
                      }
                    />
                    <FormControlLabel
                      control={
                        <Switch
                          size="small"
                          checked={!!pref.email_enabled}
                          onChange={(e) =>
                            updatePref.mutate({
                              id: pref.id,
                              data: { email_enabled: e.target.checked },
                            })
                          }
                        />
                      }
                      label={
                        <Stack direction="row" spacing={1} alignItems="center">
                          <Mail size={16} />
                          <Typography variant="body2">{t("auth.email")}</Typography>
                        </Stack>
                      }
                    />
                    <FormControlLabel
                      control={
                        <Switch
                          size="small"
                          checked={
                            !!(pref as { digest_enabled?: boolean }).digest_enabled
                          }
                          onChange={(e) =>
                            updatePref.mutate({
                              id: pref.id,
                              data: { digest_enabled: e.target.checked },
                            })
                          }
                        />
                      }
                      label={
                        <Stack direction="row" spacing={1} alignItems="center">
                          <MailPlus size={16} />
                          <Typography variant="body2">
                            {t("p.misc.notifications.dailyDigest")}
                          </Typography>
                        </Stack>
                      }
                    />
                    {!!(pref as { digest_enabled?: boolean }).digest_enabled && (
                      <TextField
                        select
                        size="small"
                        value={
                          (pref as { digest_frequency?: string }).digest_frequency ||
                          "daily"
                        }
                        onChange={(e) =>
                          updatePref.mutate({
                            id: pref.id,
                            data: { digest_frequency: e.target.value },
                          })
                        }
                        sx={{ minWidth: 110 }}
                        aria-label={t("p.misc.notifications.digestFrequency")}
                      >
                        <MenuItem value="daily">
                          {t("p.misc.notifications.digestDaily")}
                        </MenuItem>
                        <MenuItem value="weekly">
                          {t("p.misc.notifications.digestWeekly")}
                        </MenuItem>
                      </TextField>
                    )}
                  </Stack>
                </Paper>
              ))}
            </Stack>
          )}
        </Box>
      )}
    </Box>
  );
}
