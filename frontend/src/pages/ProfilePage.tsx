import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  Box,
  Typography,
  Button,
  TextField,
  MenuItem,
  Card,
  CardContent,
  Stack,
  Avatar,
  Alert,
  Divider,
  IconButton,
  InputAdornment,
  Switch,
  FormControlLabel,
  Tooltip,
  useTheme,
} from "@mui/material";
import {
  User as UserIcon,
  Lock,
  Eye,
  EyeOff,
  AlertTriangle,
  Trash2,
  MailCheck,
  BellRing,
  MailPlus,
  Mail,
  Copy,
  RotateCw,
  Clock,
  PlaneTakeoff,
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { authApi } from "../api/auth";
import {
  userApi,
  notificationsApi,
  type ApiError,
  type ApiPayload,
} from "../api/resources";
import { useWeeklyCapacity } from "../api/featComp";
import { meOooApi, type UserMeOoo } from "../api/featTask3";
import type { NotificationPreference } from "../types";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import {
  isPushSupported,
  isSubscribed,
  subscribePush,
  unsubscribePush,
  getVapidKey,
  PushError,
} from "../push";
import { useTranslation } from "react-i18next";
import "../i18n";

interface FormValues {
  username: string;
  timezone: string;
  locale: string;
}

const LOCALES = [
  { value: "es", label: "Español" },
  { value: "en", label: "English" },
  { value: "fr", label: "Français" },
  { value: "de", label: "Deutsch" },
  { value: "it", label: "Italiano" },
  { value: "pt", label: "Português" },
];

const TIMEZONES = [
  "UTC",
  "Europe/Madrid",
  "Europe/London",
  "America/New_York",
  "America/Mexico_City",
  "Asia/Tokyo",
];

export default function ProfilePage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { user } = useAuth();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [pwForm, setPwForm] = useState({
    current_password: "",
    new_password: "",
    confirm: "",
  });
  const [pwError, setPwError] = useState("");
  const [dangerPw, setDangerPw] = useState("");
  const [pushSupported] = useState(() => isPushSupported());
  const [notifPerm, setNotifPerm] = useState<NotificationPermission | null>(() =>
    typeof Notification === "undefined" ? null : Notification.permission,
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    defaultValues: {
      username: user?.username || "",
      timezone: user?.timezone || "UTC",
      locale: user?.locale || "es",
    },
  });

  const save = useMutation({
    mutationFn: (v: FormValues) => authApi.updateMe(v),
    onSuccess: () => {
      notify.success(t("p.misc.profile.updated"));
      qc.invalidateQueries({ queryKey: ["me"] });
    },
    onError: () => notify.error(t("p.misc.profile.updateError")),
  });

  const changePw = useMutation({
    mutationFn: () =>
      authApi.changePassword(pwForm.current_password, pwForm.new_password),
    onSuccess: () => {
      notify.success(t("p.misc.profile.passwordUpdated"));
      setPwForm({ current_password: "", new_password: "", confirm: "" });
      setPwError("");
    },
    onError: (e: ApiError) => {
      const msg = e.response?.data?.error || t("p.misc.profile.passwordChangeError");
      setPwError(msg);
      notify.error(msg);
    },
  });

  const verifyMut = useMutation({
    mutationFn: () => authApi.sendVerificationEmail(),
    onSuccess: () => notify.success(t("p.misc.profile.verificationSent")),
    onError: () => notify.error(t("p.misc.profile.verificationError")),
  });

  const deactivate = useMutation({
    mutationFn: () => userApi.deactivate(dangerPw),
    onSuccess: () => {
      notify.success(t("p.misc.profile.deactivated"));
      setTimeout(() => (window.location.href = "/login"), 1500);
    },
    onError: (e: ApiError) =>
      notify.error(e.response?.data?.error || t("p.misc.profile.deactivateError")),
  });

  const deleteAccount = useMutation({
    mutationFn: () => userApi.deleteAccount(dangerPw),
    onSuccess: () => {
      notify.success(t("p.misc.profile.deleted"));
      setTimeout(() => (window.location.href = "/login"), 1500);
    },
    onError: (e: ApiError) =>
      notify.error(e.response?.data?.error || t("p.misc.profile.deleteError")),
  });

  // --- Notificaciones push ---
  const vapidQuery = useQuery({
    queryKey: ["push-vapid-key"],
    queryFn: getVapidKey,
    enabled: pushSupported,
    staleTime: Infinity,
  });
  const pushStatus = useQuery({
    queryKey: ["push-subscription"],
    queryFn: isSubscribed,
    enabled: pushSupported,
  });
  const pushToggle = useMutation({
    mutationFn: async (enable: boolean) => {
      if (enable) {
        await subscribePush();
      } else {
        await unsubscribePush();
      }
    },
    onSuccess: (_data, enable) => {
      notify.success(t(enable ? "p.push.subscribed" : "p.push.unsubscribed"));
      qc.invalidateQueries({ queryKey: ["push-subscription"] });
    },
    onError: (e: Error, enable) => {
      const code = e instanceof PushError ? e.code : null;
      if (code === "permission-denied") {
        notify.error(t("p.push.permissionDenied"));
      } else if (code === "not-configured") {
        notify.error(t("p.push.noServerKey"));
      } else {
        notify.error(t(enable ? "p.push.subscribeError" : "p.push.unsubscribeError"));
      }
      qc.invalidateQueries({ queryKey: ["push-subscription"] });
    },
    onSettled: () => {
      if (typeof Notification !== "undefined") {
        setNotifPerm(Notification.permission);
      }
    },
  });
  const pushOn = !!pushStatus.data;
  const pushSwitchDisabled =
    pushToggle.isPending ||
    pushStatus.isLoading ||
    vapidQuery.isLoading ||
    notifPerm === "denied" ||
    vapidQuery.data === null;

  // --- Email → tarea: dirección personal que crea tareas al recibir correo ---
  const [emailTokenLocal, setEmailTokenLocal] = useState<string | null | undefined>();
  const inboundToken =
    emailTokenLocal !== undefined
      ? emailTokenLocal
      : ((user as { inbound_email_token?: string | null })?.inbound_email_token ?? null);
  const emailAddress = inboundToken ? `task-${inboundToken}@todolist.local` : "";
  const emailTokenMut = useMutation({
    mutationFn: (action: "rotate" | "revoke") =>
      action === "rotate" ? userApi.emailToken() : userApi.emailTokenRevoke(),
    onSuccess: (data, action) => {
      if (action === "rotate") {
        const tok = (data as { inbound_email_token?: string }).inbound_email_token;
        setEmailTokenLocal(tok ?? null);
        notify.success(t("p.public.email.generated"));
      } else {
        setEmailTokenLocal(null);
        notify.success(t("p.public.email.revoked"));
      }
    },
    onError: () => notify.error(t("p.public.email.error")),
  });

  // --- Capacidad semanal (weekly_capacity_hours en /users/me/) ---
  // capacityInput es un override local: null hasta que el usuario edita.
  const weeklyCapacity = useWeeklyCapacity();
  const [capacityInput, setCapacityInput] = useState<string | null>(null);
  const capacityValue =
    capacityInput ??
    (weeklyCapacity.capacity !== undefined ? String(weeklyCapacity.capacity) : "");
  const capacityNum = Number(capacityValue);
  const capacityValid =
    capacityValue !== "" &&
    Number.isFinite(capacityNum) &&
    capacityNum >= 1 &&
    capacityNum <= 80;
  const submitCapacity = () => {
    if (!capacityValid) return;
    weeklyCapacity.save.mutate(capacityNum, {
      onSuccess: () => notify.success(t("p.org.capacity.saved")),
      onError: () => notify.error(t("p.org.capacity.saveError")),
    });
  };

  // --- Fuera de la oficina (out_of_office en /users/me/) ---
  // Misma queryKey ["me"] que useWeeklyCapacity: el endpoint es el mismo,
  // así que ambas lecturas comparten cache y la invalidación es común.
  const { data: meOoo } = useQuery({ queryKey: ["me"], queryFn: meOooApi.get });
  const [oooLocal, setOooLocal] = useState<{ on: boolean; until: string } | null>(null);
  const oooOn = oooLocal?.on ?? !!meOoo?.out_of_office;
  const oooUntil = oooLocal?.until ?? meOoo?.out_of_office_until ?? "";
  const oooMut = useMutation({
    mutationFn: (patch: UserMeOoo) => meOooApi.update(patch),
    onSuccess: () => {
      notify.success(t("p.public.ooo.saved"));
      qc.invalidateQueries({ queryKey: ["me"] });
    },
    onError: () => notify.error(t("p.public.ooo.error")),
  });
  const toggleOoo = (on: boolean) => {
    const until = on ? oooUntil || null : null;
    setOooLocal({ on, until: until ?? "" });
    oooMut.mutate({ out_of_office: on, out_of_office_until: until });
  };
  const changeOooUntil = (until: string) => {
    setOooLocal({ on: oooOn, until });
    // PATCH solo con fecha completa o vacío (limpiar la fecha de regreso).
    if (until === "" || /^\d{4}-\d{2}-\d{2}$/.test(until)) {
      oooMut.mutate({ out_of_office: true, out_of_office_until: until || null });
    }
  };

  // --- Notificaciones por email (NotificationPreference.email_enabled) ---
  const { data: emailPrefData } = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: notificationsApi.preferences,
  });
  const emailPrefs: NotificationPreference[] =
    emailPrefData?.results || emailPrefData || [];
  const emailPrefMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiPayload }) =>
      notificationsApi.updatePreference(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notification-preferences"] });
      notify.success(t("p.misc.notifications.prefUpdated"));
    },
    onError: () => notify.error(t("p.misc.notifications.prefUpdateError")),
  });

  const submitPassword = () => {
    setPwError("");
    if (!pwForm.current_password || !pwForm.new_password) {
      setPwError(t("p.misc.profile.fillAllFields"));
      return;
    }
    if (pwForm.new_password.length < 8) {
      setPwError(t("p.misc.profile.passwordTooShort"));
      return;
    }
    if (pwForm.new_password !== pwForm.confirm) {
      setPwError(t("p.misc.profile.passwordMismatch"));
      return;
    }
    changePw.mutate();
  };

  return (
    <Box sx={{ maxWidth: 600 }}>
      <Typography variant="h5" fontWeight={700} mb={3}>
        {t("nav.profile")}
      </Typography>
      <Card>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" spacing={2} alignItems="center" mb={3}>
            <Avatar sx={{ width: 64, height: 64, bgcolor: "primary.main", fontSize: 28 }}>
              {user?.email?.[0]?.toUpperCase() || <UserIcon size={28} />}
            </Avatar>
            <Box>
              <Typography variant="subtitle1" fontWeight={600}>
                {user?.email}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                ID: {user?.id}
              </Typography>
            </Box>
          </Stack>

          <Box component="form" onSubmit={handleSubmit((v) => save.mutate(v))}>
            <Stack spacing={2}>
              <TextField
                label={t("p.misc.profile.username")}
                fullWidth
                error={!!errors.username}
                helperText={errors.username?.message}
                {...register("username", {
                  required: t("p.misc.profile.required"),
                  minLength: 3,
                })}
              />
              <TextField
                label={t("auth.email")}
                fullWidth
                value={user?.email || ""}
                disabled
                helperText={t("p.misc.profile.emailImmutable")}
              />
              {user?.email_verified ? (
                <Alert
                  severity="success"
                  variant="outlined"
                  icon={<MailCheck size={18} />}
                >
                  {t("p.misc.profile.emailVerified")}
                </Alert>
              ) : (
                <Alert
                  severity="warning"
                  variant="outlined"
                  action={
                    <Button
                      size="small"
                      disabled={verifyMut.isPending}
                      onClick={() => verifyMut.mutate()}
                    >
                      {t("p.misc.profile.verify")}
                    </Button>
                  }
                >
                  {t("p.misc.profile.emailUnverified")}
                </Alert>
              )}
              <TextField
                select
                label={t("p.misc.language")}
                fullWidth
                {...register("locale")}
              >
                {LOCALES.map((l) => (
                  <MenuItem key={l.value} value={l.value}>
                    {l.label}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                label={t("p.misc.profile.timezone")}
                fullWidth
                {...register("timezone")}
              >
                {TIMEZONES.map((tz) => (
                  <MenuItem key={tz} value={tz}>
                    {tz}
                  </MenuItem>
                ))}
              </TextField>
              <Button type="submit" variant="contained" disabled={save.isPending}>
                {t("p.misc.profile.saveChanges")}
              </Button>
            </Stack>
          </Box>
        </CardContent>
      </Card>

      {/* Fuera de la oficina */}
      <Card sx={{ mt: 3 }}>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center" mb={2}>
            <PlaneTakeoff size={20} style={{ color: theme.palette.primary.main }} />
            <Typography variant="h6" fontWeight={600}>
              {t("p.public.ooo.title")}
            </Typography>
          </Stack>
          <Divider sx={{ mb: 2 }} />
          <Typography variant="body2" color="text.secondary" mb={2}>
            {t("p.public.ooo.desc")}
          </Typography>
          <Stack spacing={2}>
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={oooOn}
                  disabled={oooMut.isPending}
                  onChange={(e) => toggleOoo(e.target.checked)}
                />
              }
              label={
                <Typography variant="body2" fontWeight={600}>
                  {t("p.public.ooo.switchLabel")}
                </Typography>
              }
            />
            <TextField
              type="date"
              size="small"
              label={t("p.public.ooo.untilLabel")}
              value={oooUntil}
              onChange={(e) => changeOooUntil(e.target.value)}
              disabled={!oooOn || oooMut.isPending}
              InputLabelProps={{ shrink: true }}
              helperText={t("p.public.ooo.untilHelper")}
              sx={{ maxWidth: 260 }}
            />
          </Stack>
        </CardContent>
      </Card>

      {/* Notificaciones por email */}
      <Card sx={{ mt: 3 }}>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center" mb={2}>
            <Mail size={20} style={{ color: theme.palette.primary.main }} />
            <Typography variant="h6" fontWeight={600}>
              {t("p.public.emailPrefs.title")}
            </Typography>
          </Stack>
          <Divider sx={{ mb: 2 }} />
          <Typography variant="body2" color="text.secondary" mb={1}>
            {t("p.public.emailPrefs.desc")}
          </Typography>
          {emailPrefs.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {t("p.public.emailPrefs.empty")}
            </Typography>
          ) : (
            <Stack spacing={0.5}>
              {emailPrefs.map((pref) => (
                <FormControlLabel
                  key={pref.id}
                  control={
                    <Switch
                      size="small"
                      checked={!!pref.email_enabled}
                      disabled={emailPrefMut.isPending}
                      onChange={(e) =>
                        emailPrefMut.mutate({
                          id: pref.id,
                          data: { email_enabled: e.target.checked },
                        })
                      }
                    />
                  }
                  label={
                    <Typography variant="body2">
                      {pref.notification_type
                        ? t(`p.misc.notifications.type.${pref.notification_type}`, {
                            defaultValue: pref.notification_type.replace(/_/g, " "),
                          })
                        : ""}
                    </Typography>
                  }
                />
              ))}
            </Stack>
          )}
        </CardContent>
      </Card>

      {/* Cambiar contraseña */}
      <Card sx={{ mt: 3 }}>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center" mb={2}>
            <Lock size={20} color="primary.main" />
            <Typography variant="h6" fontWeight={600}>
              {t("p.misc.profile.changePassword")}
            </Typography>
          </Stack>
          <Divider sx={{ mb: 2 }} />
          {pwError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {pwError}
            </Alert>
          )}
          <Stack spacing={2}>
            <TextField
              label={t("p.misc.profile.currentPassword")}
              type={showCurrent ? "text" : "password"}
              fullWidth
              autoComplete="current-password"
              value={pwForm.current_password}
              onChange={(e) => setPwForm({ ...pwForm, current_password: e.target.value })}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={() => setShowCurrent(!showCurrent)}>
                      {showCurrent ? <EyeOff size={18} /> : <Eye size={18} />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              label={t("p.misc.profile.newPassword")}
              type={showNew ? "text" : "password"}
              fullWidth
              autoComplete="new-password"
              value={pwForm.new_password}
              onChange={(e) => setPwForm({ ...pwForm, new_password: e.target.value })}
              helperText={t("p.misc.profile.minChars")}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={() => setShowNew(!showNew)}>
                      {showNew ? <EyeOff size={18} /> : <Eye size={18} />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              label={t("p.misc.profile.repeatPassword")}
              type={showNew ? "text" : "password"}
              fullWidth
              autoComplete="new-password"
              value={pwForm.confirm}
              onChange={(e) => setPwForm({ ...pwForm, confirm: e.target.value })}
            />
            <Button
              variant="contained"
              disabled={changePw.isPending}
              onClick={submitPassword}
            >
              {changePw.isPending
                ? t("p.misc.profile.saving")
                : t("p.misc.profile.changePassword")}
            </Button>
          </Stack>
        </CardContent>
      </Card>

      {/* Notificaciones push */}
      <Card sx={{ mt: 3 }}>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center" mb={2}>
            <BellRing size={20} style={{ color: theme.palette.primary.main }} />
            <Typography variant="h6" fontWeight={600}>
              {t("p.push.title")}
            </Typography>
          </Stack>
          <Divider sx={{ mb: 2 }} />
          {!pushSupported ? (
            <>
              <FormControlLabel
                control={<Switch size="small" disabled />}
                label={t("p.push.switchLabel")}
              />
              <Alert severity="info" variant="outlined" sx={{ mt: 1 }}>
                {t("p.push.unsupported")}
              </Alert>
            </>
          ) : (
            <Stack spacing={1.5}>
              <FormControlLabel
                control={
                  <Switch
                    size="small"
                    checked={pushOn}
                    disabled={pushSwitchDisabled}
                    onChange={(e) => pushToggle.mutate(e.target.checked)}
                  />
                }
                label={
                  <Typography variant="body2" fontWeight={600}>
                    {t("p.push.switchLabel")}
                  </Typography>
                }
              />
              <Typography variant="body2" color="text.secondary">
                {pushStatus.isLoading
                  ? t("p.push.checking")
                  : pushOn
                    ? t("p.push.statusOn")
                    : t("p.push.statusOff")}{" "}
                {t("p.push.desc")}{" "}
                {notifPerm === "default" && t("p.push.permissionRequired")}
              </Typography>
              {notifPerm === "denied" && (
                <Alert severity="warning" variant="outlined">
                  {t("p.push.permissionDenied")}
                </Alert>
              )}
              {vapidQuery.data === null && (
                <Alert severity="info" variant="outlined">
                  {t("p.push.noServerKey")}
                </Alert>
              )}
            </Stack>
          )}
        </CardContent>
      </Card>

      {/* Email → tarea */}
      <Card sx={{ mt: 3 }}>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center" mb={2}>
            <MailPlus size={20} style={{ color: theme.palette.primary.main }} />
            <Typography variant="h6" fontWeight={600}>
              {t("p.public.email.title")}
            </Typography>
          </Stack>
          <Divider sx={{ mb: 2 }} />
          <Typography variant="body2" color="text.secondary" mb={2}>
            {t("p.public.email.desc")}
          </Typography>
          {inboundToken ? (
            <Stack direction="row" spacing={1} alignItems="center">
              <TextField
                size="small"
                fullWidth
                value={emailAddress}
                InputProps={{ readOnly: true }}
              />
              <Tooltip title={t("p.public.email.copy")}>
                <IconButton
                  onClick={() =>
                    navigator.clipboard.writeText(emailAddress).then(
                      () => notify.success(t("p.public.email.copied")),
                      () => {},
                    )
                  }
                >
                  <Copy size={16} />
                </IconButton>
              </Tooltip>
              <Tooltip title={t("p.public.email.rotate")}>
                <IconButton onClick={() => emailTokenMut.mutate("rotate")}>
                  <RotateCw size={16} />
                </IconButton>
              </Tooltip>
            </Stack>
          ) : (
            <Button
              variant="outlined"
              onClick={() => emailTokenMut.mutate("rotate")}
              disabled={emailTokenMut.isPending}
            >
              {t("p.public.email.generate")}
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Capacidad semanal */}
      <Card sx={{ mt: 3 }}>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center" mb={2}>
            <Clock size={20} style={{ color: theme.palette.primary.main }} />
            <Typography variant="h6" fontWeight={600}>
              {t("p.org.capacity.title")}
            </Typography>
          </Stack>
          <Divider sx={{ mb: 2 }} />
          <Typography variant="body2" color="text.secondary" mb={2}>
            {t("p.org.capacity.desc")}
          </Typography>
          <Stack direction="row" spacing={1.5} alignItems="flex-start">
            <TextField
              type="number"
              size="small"
              label={t("p.org.capacity.field")}
              value={capacityValue}
              onChange={(e) => setCapacityInput(e.target.value)}
              error={capacityValue !== "" && !capacityValid}
              helperText={
                capacityValue !== "" && !capacityValid
                  ? t("p.org.capacity.invalid")
                  : t("p.org.capacity.hint")
              }
              inputProps={{ min: 1, max: 80 }}
              sx={{ maxWidth: 240 }}
            />
            <Button
              variant="contained"
              disabled={!capacityValid || weeklyCapacity.save.isPending}
              onClick={submitCapacity}
            >
              {t("common.save")}
            </Button>
          </Stack>
        </CardContent>
      </Card>

      {/* Zona de peligro */}
      <Card sx={{ mt: 3, borderColor: "error.main" }}>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center" mb={2}>
            <AlertTriangle size={20} style={{ color: theme.palette.error.main }} />
            <Typography variant="h6" fontWeight={600} color="error.main">
              {t("p.misc.dangerZone")}
            </Typography>
          </Stack>
          <Divider sx={{ mb: 2 }} />
          <TextField
            label={t("p.misc.profile.dangerPasswordLabel")}
            type="password"
            fullWidth
            size="small"
            autoComplete="current-password"
            value={dangerPw}
            onChange={(e) => setDangerPw(e.target.value)}
            sx={{ mb: 2 }}
          />
          <Stack spacing={2}>
            <Box>
              <Typography variant="subtitle2" fontWeight={600}>
                {t("p.misc.profile.deactivateAccount")}
              </Typography>
              <Typography variant="body2" color="text.secondary" mb={1}>
                {t("p.misc.profile.deactivateDesc")}
              </Typography>
              <Button
                variant="outlined"
                color="warning"
                disabled={deactivate.isPending}
                onClick={async () => {
                  if (
                    await confirm(t("p.misc.profile.confirmDeactivate"), {
                      confirmLabel: t("p.misc.profile.deactivate"),
                    })
                  )
                    deactivate.mutate();
                }}
              >
                {deactivate.isPending
                  ? t("p.misc.profile.deactivating")
                  : t("p.misc.profile.deactivateAccount")}
              </Button>
            </Box>
            <Box>
              <Typography variant="subtitle2" fontWeight={600}>
                {t("p.misc.profile.deleteAccount")}
              </Typography>
              <Typography variant="body2" color="text.secondary" mb={1}>
                {t("p.misc.profile.deleteDesc")}
              </Typography>
              <Button
                variant="outlined"
                color="error"
                startIcon={<Trash2 size={16} />}
                disabled={deleteAccount.isPending}
                onClick={async () => {
                  if (
                    await confirm(t("p.misc.profile.confirmDeleteMsg"), {
                      title: t("p.misc.profile.deletePermanently"),
                      requireText: t("p.misc.profile.deleteConfirmText"),
                      confirmLabel: t("p.misc.profile.deleteMyAccount"),
                    })
                  )
                    deleteAccount.mutate();
                }}
              >
                {deleteAccount.isPending
                  ? t("p.misc.profile.deleting")
                  : t("p.misc.profile.deletePermanently")}
              </Button>
            </Box>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
