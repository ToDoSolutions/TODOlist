import { useState, useRef } from "react";
import {
  IconButton,
  Badge,
  Popover,
  Box,
  Typography,
  Stack,
  Chip,
  Button,
  Divider,
  CircularProgress,
  Paper,
} from "@mui/material";
import { Bell, CheckCheck } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notificationsApi } from "../api/resources";

const TYPE_LABELS: Record<string, string> = {
  task_assigned: "Asignada",
  task_due_soon: "Por vencer",
  task_overdue: "Vencida",
  task_completed: "Completada",
  task_commented: "Comentario",
  task_blocked: "Bloqueada",
  sprint_started: "Sprint iniciado",
  sprint_ending: "Sprint por terminar",
  sprint_closed: "Sprint cerrado",
  mention: "Mención",
  pr_opened: "PR abierto",
  pr_merged: "PR fusionado",
  pr_review_requested: "Review solicitada",
  ci_failed: "CI fallida",
  release_published: "Release",
  automation_triggered: "Automatización",
  custom: "Notificación",
};

function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (diff < 60) return "ahora";
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

export default function NotificationBell() {
  const qc = useQueryClient();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const open = Boolean(anchorEl);

  const { data: unreadData } = useQuery({
    queryKey: ["notifications-unread"],
    queryFn: notificationsApi.unreadCount,
    refetchInterval: 30000,
  });

  const { data: notifications, isLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: notificationsApi.list,
    enabled: open,
  });

  const markAllRead = useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["notifications-unread"] });
    },
  });

  const markRead = useMutation({
    mutationFn: notificationsApi.markRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["notifications-unread"] });
    },
  });

  const unreadCount = unreadData?.count || 0;
  const notifList = notifications?.results || notifications || [];

  return (
    <>
      <IconButton
        onClick={(e) => setAnchorEl(e.currentTarget)}
        sx={{ color: "text.secondary" }}
      >
        <Badge badgeContent={unreadCount} color="error">
          <Bell size={22} />
        </Badge>
      </IconButton>
      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        PaperProps={{ sx: { width: 380, maxHeight: 500 } }}
      >
        <Stack direction="row" alignItems="center" justifyContent="space-between" p={1.5}>
          <Typography variant="subtitle1" fontWeight={700}>
            Notificaciones {unreadCount > 0 && `(${unreadCount})`}
          </Typography>
          {unreadCount > 0 && (
            <Button
              size="small"
              startIcon={<CheckCheck size={14} />}
              onClick={() => markAllRead.mutate()}
            >
              Marcar todas
            </Button>
          )}
        </Stack>
        <Divider />
        <Box sx={{ maxHeight: 400, overflowY: "auto" }}>
          {isLoading ? (
            <Box display="flex" justifyContent="center" py={3}>
              <CircularProgress size={24} />
            </Box>
          ) : notifList.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ p: 3, textAlign: "center" }}>
              No tienes notificaciones
            </Typography>
          ) : (
            notifList.slice(0, 30).map((n: any) => (
              <Paper
                key={n.id}
                variant="outlined"
                square
                sx={{
                  p: 1.5,
                  cursor: "pointer",
                  bgcolor: n.read ? "transparent" : "action.hover",
                  borderLeft: n.read ? "3px solid transparent" : "3px solid primary.main",
                  "&:hover": { bgcolor: "action.selected" },
                }}
                onClick={() => {
                  if (!n.read) markRead.mutate(n.id);
                  if (n.action_url) window.location.hash = n.action_url;
                }}
              >
                <Stack direction="row" alignItems="flex-start" spacing={1}>
                  <Box flex={1}>
                    <Stack direction="row" spacing={0.5} alignItems="center" mb={0.5}>
                      <Chip
                        size="small"
                        label={TYPE_LABELS[n.type] || n.type}
                        sx={{ height: 16, fontSize: 9 }}
                        variant="outlined"
                      />
                      <Typography variant="caption" color="text.secondary">
                        {timeAgo(n.created_at)}
                      </Typography>
                    </Stack>
                    <Typography variant="body2" fontWeight={n.read ? 400 : 600} noWrap>
                      {n.title}
                    </Typography>
                    {n.body && (
                      <Typography variant="caption" color="text.secondary" noWrap>
                        {n.body}
                      </Typography>
                    )}
                  </Box>
                </Stack>
              </Paper>
            ))
          )}
        </Box>
      </Popover>
    </>
  );
}
