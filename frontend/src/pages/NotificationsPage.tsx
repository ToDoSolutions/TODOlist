import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notificationsApi } from "../api/resources";
import { notify } from "../notify";
import {
  Box,
  Typography,
  Paper,
  Button,
  Stack,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Switch,
  FormControlLabel,
  Chip,
  Tabs,
  Tab,
  Divider,
} from "@mui/material";
import { Bell, CheckCheck, Mail, BellOff, Settings } from "lucide-react";

export default function NotificationsPage() {
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
      notify.success("Todas marcadas como leídas");
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
    mutationFn: ({ id, data }: { id: number; data: any }) =>
      notificationsApi.updatePreference(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notification-preferences"] });
      notify.success("Preferencia actualizada");
    },
    onError: () => notify.error("No se pudo actualizar la preferencia"),
  });

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} mb={3}>
        Notificaciones
      </Typography>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
        <Tab icon={<Bell size={16} />} iconPosition="start" label="Historial" />
        <Tab icon={<Settings size={16} />} iconPosition="start" label="Preferencias" />
      </Tabs>

      {/* Tab 1: Historial */}
      {tab === 0 && (
        <Box>
          <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="body2" color="text.secondary">
              {notifications.length} notificaciones
            </Typography>
            <Button
              size="small"
              startIcon={<CheckCheck size={16} />}
              onClick={() => markAllRead.mutate()}
              disabled={markAllRead.isPending}
            >
              Marcar todas leídas
            </Button>
          </Stack>

          {notifLoading ? (
            <CircularProgress />
          ) : notifications.length === 0 ? (
            <Alert severity="info">No hay notificaciones.</Alert>
          ) : (
            <Stack spacing={1}>
              {notifications.map((n: any) => (
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
                          label={n.type?.replace(/_/g, " ")}
                          sx={{ height: 20, fontSize: 10 }}
                        />
                        <Typography variant="caption" color="text.secondary">
                          {n.created_at && new Date(n.created_at).toLocaleString("es-ES")}
                        </Typography>
                      </Stack>
                    </Box>
                    <Stack direction="row" spacing={0.5}>
                      {n.read ? (
                        <Tooltip title="Marcar no leída">
                          <IconButton size="small" onClick={() => markUnread.mutate(n.id)}>
                            <BellOff size={16} />
                          </IconButton>
                        </Tooltip>
                      ) : (
                        <Tooltip title="Marcar leída">
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
        </Box>
      )}

      {/* Tab 2: Preferencias */}
      {tab === 1 && (
        <Box>
          <Typography variant="body2" color="text.secondary" mb={2}>
            Configura qué notificaciones quieres recibir y por qué canal.
          </Typography>
          {prefLoading ? (
            <CircularProgress />
          ) : preferences.length === 0 ? (
            <Alert severity="info">
              No hay preferencias configuradas. Se usarán los valores por defecto.
            </Alert>
          ) : (
            <Stack spacing={1}>
              {preferences.map((pref: any) => (
                <Paper key={pref.id} variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="subtitle2" fontWeight={600} mb={1}>
                    {pref.notification_type?.replace(/_/g, " ")}
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
                          <Typography variant="body2">In-app</Typography>
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
                          <Typography variant="body2">Email</Typography>
                        </Stack>
                      }
                    />
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
