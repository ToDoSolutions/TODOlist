import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Stack,
  Paper,
  Button,
  Tabs,
  Tab,
  Chip,
  Divider,
} from "@mui/material";
import {
  AtSign,
  MailWarning,
  GitCompareArrows,
  ShieldAlert,
  CheckCheck,
} from "lucide-react";
import { formatRelative } from "../lib/dates";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState, ErrorState } from "../components/ui/states";
import { TaskListSkeleton } from "../components/ui/skeletons";
import {
  collaborationApi,
  invitationsApi,
  syncOperationsApi,
  notificationsApi,
} from "../api/resources";
import type {
  MentionItem,
  Invitation,
  SyncOperationItem,
  AppNotification,
} from "../types";
import { notify } from "../notify";

type TabKey = "all" | "mentions" | "invitations" | "conflicts" | "alerts";

const TABS: { key: TabKey; labelKey: string }[] = [
  { key: "all", labelKey: "p.work.attention.tabs.all" },
  { key: "mentions", labelKey: "p.work.attention.tabs.mentions" },
  { key: "invitations", labelKey: "p.work.attention.tabs.invitations" },
  { key: "conflicts", labelKey: "p.work.attention.tabs.conflicts" },
  { key: "alerts", labelKey: "p.work.attention.tabs.alerts" },
];

/**
 * Bandeja de atención: elementos que requieren una ACCIÓN del usuario.
 * Distinto de Notificaciones (historial informativo) y de Mi trabajo (tareas).
 */
export default function AttentionPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>("all");

  const mentionsQ = useQuery({
    queryKey: ["mentions"],
    queryFn: collaborationApi.mentions.list,
  });
  const mentions: MentionItem[] = mentionsQ.data ?? [];

  const invitationsQ = useQuery({
    queryKey: ["invitations"],
    queryFn: invitationsApi.list,
  });
  const invitations: Invitation[] = (invitationsQ.data ?? []).filter(
    (i) => (i as Invitation).status === "pending",
  );

  const syncQ = useQuery({
    queryKey: ["sync-operations"],
    queryFn: syncOperationsApi.list,
  });
  const conflicts: SyncOperationItem[] = (syncQ.data ?? []).filter(
    (o) => o.status === "conflict",
  );

  const notifQ = useQuery({
    queryKey: ["notifications"],
    queryFn: notificationsApi.list,
  });
  const alerts: AppNotification[] = (notifQ.data ?? []).filter((n) => !n.read);

  const isLoading =
    mentionsQ.isLoading ||
    invitationsQ.isLoading ||
    syncQ.isLoading ||
    notifQ.isLoading;
  const isError =
    mentionsQ.isError || invitationsQ.isError || syncQ.isError || notifQ.isError;

  const respondInvitation = useMutation({
    mutationFn: ({ id, accept }: { id: number; accept: boolean }) =>
      accept ? invitationsApi.accept(id) : invitationsApi.decline(id),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: ["invitations"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
      notify.success(
        v.accept
          ? t("p.work.attention.invitationAccepted")
          : t("p.work.attention.invitationDeclined"),
      );
    },
    onError: () => notify.error(t("p.work.attention.respondError")),
  });

  const markAllRead = useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      notify.success(t("p.work.attention.alertsMarkedRead"));
    },
  });

  const counts = {
    mentions: mentions.length,
    invitations: invitations.length,
    conflicts: conflicts.length,
    alerts: alerts.length,
  };
  const total = counts.mentions + counts.invitations + counts.conflicts + counts.alerts;

  const show = useMemo(
    () => ({
      mentions: tab === "all" || tab === "mentions",
      invitations: tab === "all" || tab === "invitations",
      conflicts: tab === "all" || tab === "conflicts",
      alerts: tab === "all" || tab === "alerts",
    }),
    [tab],
  );

  const ago = (iso?: string) => (iso ? formatRelative(iso) : "");

  return (
    <Box>
      <PageHeader
        title={t("p.work.attention.title")}
        description={t("p.work.attention.desc", { count: total })}
        breadcrumbs={[
          { label: t("p.work.attention.breadcrumbArea") },
          { label: t("p.work.attention.title") },
        ]}
        actions={
          alerts.length > 0 ? (
            <Button
              variant="outlined"
              startIcon={<CheckCheck size={15} />}
              onClick={() => markAllRead.mutate()}
              disabled={markAllRead.isPending}
            >
              {t("p.work.attention.markRead")}
            </Button>
          ) : undefined
        }
      />

      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v as TabKey)}
        sx={{ mb: 3 }}
        variant="scrollable"
        scrollButtons="auto"
      >
        {TABS.map((item) => (
          <Tab
            key={item.key}
            value={item.key}
            label={
              item.key === "all"
                ? `${t(item.labelKey)} (${total})`
                : `${t(item.labelKey)} (${counts[item.key as keyof typeof counts]})`
            }
          />
        ))}
      </Tabs>

      {isLoading ? (
        <TaskListSkeleton rows={5} />
      ) : isError ? (
        <ErrorState
          title={t("p.work.attention.loadError")}
          onRetry={() => {
            void mentionsQ.refetch();
            void invitationsQ.refetch();
            void syncQ.refetch();
            void notifQ.refetch();
          }}
        />
      ) : total === 0 ? (
        <EmptyState
          title={t("p.work.attention.emptyTitle")}
          description={t("p.work.attention.emptyDesc")}
        />
      ) : (
        <Stack spacing={1.5}>
          {show.mentions &&
            mentions.map((m) => (
              <Paper key={`m-${m.id}`} variant="outlined" sx={{ p: 1.5 }}>
                <Stack direction="row" spacing={1.5} alignItems="flex-start">
                  <AtSign size={18} color="#1976d2" style={{ marginTop: 2 }} />
                  <Box flex={1} minWidth={0}>
                    <Typography variant="body2">
                      {t("p.work.attention.mentionedIn", {
                        author:
                          m.author_display ??
                          m.author_email ??
                          t("p.work.attention.someone"),
                        task: m.task_title ?? t("p.work.attention.taskN", { id: m.task }),
                      })}
                    </Typography>
                    {m.content && (
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{ fontStyle: "italic" }}
                      >
                        “{m.content.slice(0, 140)}”
                      </Typography>
                    )}
                    <Typography variant="caption" color="text.secondary">
                      {ago(m.created_at)}
                    </Typography>
                  </Box>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => navigate(`/app/tasks/${m.task}`)}
                  >
                    {t("p.work.attention.openTask")}
                  </Button>
                </Stack>
              </Paper>
            ))}

          {show.invitations &&
            invitations.map((inv) => (
              <Paper key={`i-${inv.id}`} variant="outlined" sx={{ p: 1.5 }}>
                <Stack direction="row" spacing={1.5} alignItems="center">
                  <MailWarning size={18} color="#ed6c02" />
                  <Box flex={1} minWidth={0}>
                    <Typography variant="body2">
                      {inv.target_name
                        ? t("p.work.attention.pendingInvitationTo", {
                            name: inv.target_name,
                          })
                        : t("p.work.attention.pendingInvitation")}
                      {inv.role
                        ? t("p.work.attention.roleSuffix", {
                            role: t(`p.work.attention.role.${inv.role}`, {
                              defaultValue: inv.role,
                            }),
                          })
                        : ""}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {inv.invited_by_email
                        ? t("p.work.attention.invitedBy", {
                            email: inv.invited_by_email,
                            ago: ago(inv.created_at),
                          })
                        : ago(inv.created_at)}
                    </Typography>
                  </Box>
                  <Button
                    size="small"
                    variant="contained"
                    disabled={respondInvitation.isPending}
                    onClick={() => respondInvitation.mutate({ id: inv.id, accept: true })}
                  >
                    {t("p.work.attention.accept")}
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    disabled={respondInvitation.isPending}
                    onClick={() =>
                      respondInvitation.mutate({ id: inv.id, accept: false })
                    }
                  >
                    {t("p.work.attention.decline")}
                  </Button>
                </Stack>
              </Paper>
            ))}

          {show.conflicts &&
            conflicts.map((c) => (
              <Paper key={`c-${c.id}`} variant="outlined" sx={{ p: 1.5 }}>
                <Stack direction="row" spacing={1.5} alignItems="center">
                  <GitCompareArrows size={18} color="#d32f2f" />
                  <Box flex={1} minWidth={0}>
                    <Typography variant="body2">
                      {t("p.work.attention.syncConflict", {
                        entity: c.entity_type ?? t("p.work.attention.entity"),
                        suffix: c.entity_id ? ` #${c.entity_id}` : "",
                      })}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {ago(c.created_at)}
                    </Typography>
                  </Box>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => navigate("/app/offline-sync")}
                  >
                    {t("p.work.attention.resolve")}
                  </Button>
                </Stack>
              </Paper>
            ))}

          {show.alerts &&
            alerts.slice(0, 20).map((n) => (
              <Paper key={`n-${n.id}`} variant="outlined" sx={{ p: 1.5 }}>
                <Stack direction="row" spacing={1.5} alignItems="flex-start">
                  <ShieldAlert size={18} color="#9c27b0" style={{ marginTop: 2 }} />
                  <Box flex={1} minWidth={0}>
                    <Typography variant="body2" fontWeight={600}>
                      {n.title ?? t("p.work.attention.notification")}
                    </Typography>
                    {n.body && (
                      <Typography variant="body2" color="text.secondary">
                        {n.body}
                      </Typography>
                    )}
                    <Typography variant="caption" color="text.secondary">
                      {ago(n.created_at)}
                    </Typography>
                  </Box>
                  {n.type && (
                    <Chip
                      size="small"
                      label={t(`p.misc.notifications.type.${n.type}`, {
                        defaultValue: n.type.replace(/_/g, " "),
                      })}
                      variant="outlined"
                    />
                  )}
                  <Button
                    size="small"
                    onClick={() => {
                      notificationsApi
                        .markRead(n.id)
                        .then(() =>
                          qc.invalidateQueries({ queryKey: ["notifications"] }),
                        )
                        .catch(() =>
                          notify.error(t("p.work.attention.respondError")),
                        );
                      if (n.action_url) navigate(n.action_url);
                    }}
                  >
                    {n.action_url
                      ? t("p.work.attention.open")
                      : t("p.work.attention.dismiss")}
                  </Button>
                </Stack>
              </Paper>
            ))}

          <Divider sx={{ my: 1 }} />
          <Typography variant="caption" color="text.secondary">
            {t("p.work.attention.footer")}
          </Typography>
        </Stack>
      )}
    </Box>
  );
}
