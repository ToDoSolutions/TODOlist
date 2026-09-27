import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Paper,
  Typography,
  Button,
  Stack,
  Chip,
  CircularProgress,
  Alert,
  Divider,
} from "@mui/material";
import { Mail, Check, X, ArrowLeft } from "lucide-react";
import { format, parseISO, isPast } from "date-fns";
import { es } from "date-fns/locale";
import { useTranslation } from "react-i18next";
import "../i18n";
import { invitationsApi, projectsApi } from "../api/resources";
import { notify } from "../notify";

interface Invitation {
  id: number;
  target_type: "project" | "team";
  target_id: number;
  email: string;
  role: string;
  invited_by: number;
  status: "pending" | "accepted" | "declined" | "expired";
  created_at: string;
  responded_at: string | null;
}

/** Página de destino para invitaciones (deep link desde email/notificación).
 *  Muestra detalle + acciones, y estados diferenciados: caducada,
 *  ya respondida, no encontrada. */
export default function InvitationPage() {
  const { t } = useTranslation();
  const { invitationId } = useParams();
  const id = Number(invitationId);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [acted, setActed] = useState<"accepted" | "declined" | null>(null);

  const ROLE_LABELS: Record<string, string> = {
    owner: t("p.auth.invitation.roles.owner"),
    admin: t("p.auth.invitation.roles.admin"),
    editor: t("p.auth.invitation.roles.editor"),
    viewer: t("p.auth.invitation.roles.viewer"),
    member: t("p.auth.invitation.roles.member"),
    guest: t("p.auth.invitation.roles.guest"),
  };

  const STATUS_LABELS: Record<
    string,
    { label: string; severity: "info" | "success" | "warning" }
  > = {
    accepted: {
      label: t("p.auth.invitation.status.accepted"),
      severity: "success",
    },
    declined: {
      label: t("p.auth.invitation.status.declined"),
      severity: "info",
    },
    expired: { label: t("p.auth.invitation.status.expired"), severity: "warning" },
  };

  const { data: invitations, isLoading } = useQuery({
    queryKey: ["invitations"],
    queryFn: invitationsApi.list,
  });
  const invitation = (Array.isArray(invitations) ? invitations : []).find(
    (i) => (i as Invitation).id === id,
  ) as Invitation | undefined;

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
    enabled: !!invitation && invitation.target_type === "project",
  });
  const targetProject = (Array.isArray(projectsData) ? projectsData : []).find(
    (p) => p.id === invitation?.target_id,
  );

  const acceptMut = useMutation({
    mutationFn: () => invitationsApi.accept(id),
    onSuccess: () => {
      setActed("accepted");
      qc.invalidateQueries({ queryKey: ["invitations"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
      notify.success(t("p.auth.invitation.accepted"));
    },
    onError: () => notify.error(t("p.auth.invitation.errors.accept")),
  });
  const declineMut = useMutation({
    mutationFn: () => invitationsApi.decline(id),
    onSuccess: () => {
      setActed("declined");
      qc.invalidateQueries({ queryKey: ["invitations"] });
      notify.success(t("p.auth.invitation.declined"));
    },
    onError: () => notify.error(t("p.auth.invitation.errors.decline")),
  });

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" py={10}>
        <CircularProgress />
      </Box>
    );
  }

  if (!invitation) {
    return (
      <Box maxWidth={480} mx="auto" py={8} px={2}>
        <Alert severity="warning" sx={{ mb: 2 }}>
          {t("p.auth.invitation.notFound")}
        </Alert>
        <Button startIcon={<ArrowLeft size={16} />} onClick={() => navigate("/app")}>
          {t("p.auth.invitation.goHome")}
        </Button>
      </Box>
    );
  }

  const statusInfo = STATUS_LABELS[acted ?? invitation.status];
  const pending = invitation.status === "pending" && !acted;
  const busy = acceptMut.isPending || declineMut.isPending;
  const createdAgo = format(parseISO(invitation.created_at), "d MMM yyyy", {
    locale: es,
  });
  const targetName =
    invitation.target_type === "project"
      ? targetProject?.name ||
        t("p.auth.invitation.targetProject", { id: invitation.target_id })
      : t("p.auth.invitation.targetTeam", { id: invitation.target_id });

  return (
    <Box display="flex" justifyContent="center" py={6} px={2}>
      <Paper variant="outlined" sx={{ p: 4, maxWidth: 480, width: "100%" }}>
        <Stack spacing={2.5} alignItems="center" textAlign="center">
          <Mail size={40} color="#1976d2" />
          <Typography variant="h5" fontWeight={700}>
            {t("p.auth.invitation.title")}
          </Typography>

          {statusInfo ? (
            <Alert severity={statusInfo.severity} sx={{ width: "100%" }}>
              {statusInfo.label}
              {invitation.responded_at &&
                ` — ${format(parseISO(invitation.responded_at), "d MMM yyyy", { locale: es })}`}
            </Alert>
          ) : null}

          <Divider flexItem />

          <Box>
            <Typography variant="body1">
              {t("p.auth.invitation.invitedToPre")} <strong>{targetName}</strong>
            </Typography>
            <Stack direction="row" spacing={1} justifyContent="center" mt={1}>
              <Chip
                size="small"
                variant="outlined"
                label={t("p.auth.invitation.role", {
                  role: ROLE_LABELS[invitation.role] || invitation.role,
                })}
              />
              <Chip
                size="small"
                variant="outlined"
                label={t("p.auth.invitation.sentOn", { date: createdAgo })}
                color={isPast(parseISO(invitation.created_at)) ? "default" : "default"}
              />
            </Stack>
            {invitation.target_type === "project" && (
              <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                {t("p.auth.invitation.expiry")}
              </Typography>
            )}
          </Box>

          {pending && (
            <Stack direction="row" spacing={2} width="100%">
              <Button
                variant="contained"
                fullWidth
                size="large"
                startIcon={<Check size={18} />}
                disabled={busy}
                onClick={() => acceptMut.mutate()}
              >
                {t("p.auth.invitation.accept")}
              </Button>
              <Button
                variant="outlined"
                fullWidth
                size="large"
                startIcon={<X size={18} />}
                disabled={busy}
                onClick={() => declineMut.mutate()}
              >
                {t("p.auth.invitation.decline")}
              </Button>
            </Stack>
          )}

          {(acted === "accepted" || invitation.status === "accepted") &&
            invitation.target_type === "project" && (
              <Button
                variant="contained"
                fullWidth
                onClick={() => navigate(`/app/project/${invitation.target_id}`)}
              >
                {t("p.auth.invitation.goToProject")}
              </Button>
            )}

          <Button
            size="small"
            startIcon={<ArrowLeft size={16} />}
            onClick={() => navigate("/app/attention")}
          >
            {t("p.auth.invitation.viewPending")}
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
}
