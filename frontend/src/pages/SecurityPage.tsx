import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import {
  Box,
  Typography,
  Paper,
  Stack,
  Button,
  TextField,
  Alert,
  Chip,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
  useTheme,
} from "@mui/material";
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  Key,
  Smartphone,
  Copy,
  Check,
  MonitorSmartphone,
  Trash2,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { twofactorApi, offlineSyncApi } from "../api/resources";
import { formatRelative } from "../lib/dates";
import { useConfirm } from "../components/ConfirmDialog";
import { notify } from "../notify";
import { useTranslation } from "react-i18next";

export default function SecurityPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();
  const [setupData, setSetupData] = useState<{
    secret?: string;
    otpauth_uri?: string;
  } | null>(null);
  const [confirmCode, setConfirmCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [disableDialog, setDisableDialog] = useState(false);
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null);
  const [copied, setCopied] = useState(false);

  const confirm = useConfirm();

  const { data: status, isLoading } = useQuery({
    queryKey: ["2fa-status"],
    queryFn: twofactorApi.status,
  });

  const { data: devices } = useQuery({
    queryKey: ["sync-devices"],
    queryFn: offlineSyncApi.listDevices,
  });

  const invalidateDevices = () => qc.invalidateQueries({ queryKey: ["sync-devices"] });

  const revokeMut = useMutation({
    mutationFn: (deviceId: string) => offlineSyncApi.revokeDevice(deviceId),
    onSuccess: () => {
      notify.success(t("p.admin.security.deviceRevoked"));
      invalidateDevices();
    },
    onError: () => notify.error(t("p.admin.security.deviceRevokeError")),
  });

  const removeMut = useMutation({
    mutationFn: (deviceId: string) => offlineSyncApi.removeDevice(deviceId),
    onSuccess: () => {
      notify.success(t("p.admin.security.deviceRemoved"));
      invalidateDevices();
    },
    onError: () => notify.error(t("p.admin.security.deviceRevokeError")),
  });

  const revokeAllMut = useMutation({
    mutationFn: offlineSyncApi.revokeAllDevices,
    onSuccess: () => {
      notify.success(t("p.admin.security.allRevoked"));
      invalidateDevices();
    },
    onError: () => notify.error(t("p.admin.security.deviceRevokeError")),
  });

  const setupMut = useMutation({
    mutationFn: twofactorApi.setup,
    onSuccess: (data) => setSetupData(data),
    onError: () => notify.error(t("p.admin.security.errorSetup")),
  });

  const confirmMut = useMutation({
    mutationFn: twofactorApi.confirm,
    onSuccess: (data) => {
      notify.success(t("p.admin.security.notifyEnabled"));
      setSetupData(null);
      setConfirmCode("");
      setBackupCodes(data.backup_codes);
      qc.invalidateQueries({ queryKey: ["2fa-status"] });
    },
    onError: () => notify.error(t("p.admin.security.invalidCode")),
  });

  const disableMut = useMutation({
    mutationFn: twofactorApi.disable,
    onSuccess: () => {
      notify.info(t("p.admin.security.notifyDisabled"));
      setDisableDialog(false);
      setDisableCode("");
      qc.invalidateQueries({ queryKey: ["2fa-status"] });
    },
    onError: () => notify.error(t("p.admin.security.invalidCode")),
  });

  const copyBackupCodes = () => {
    if (backupCodes) {
      navigator.clipboard.writeText(backupCodes.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" py={5}>
        <CircularProgress />
      </Box>
    );
  }

  const isEnabled = status?.is_enabled;

  return (
    <Box maxWidth={700} mx="auto">
      <Stack direction="row" alignItems="center" spacing={1} mb={3}>
        <Shield size={24} style={{ color: theme.palette.primary.main }} />
        <Typography variant="h5" fontWeight={700}>
          {t("nav.security")}
        </Typography>
      </Stack>

      {/* 2FA Status */}
      <Paper variant="outlined" sx={{ p: 3, mb: 2 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
          <Stack direction="row" alignItems="center" spacing={1}>
            {isEnabled ? (
              <ShieldCheck size={20} style={{ color: theme.palette.success.main }} />
            ) : (
              <ShieldAlert size={20} style={{ color: theme.palette.warning.main }} />
            )}
            <Typography variant="h6">{t("p.admin.security.tfaTitle")}</Typography>
          </Stack>
          <Chip
            size="small"
            label={
              isEnabled ? t("p.admin.security.enabled") : t("p.admin.security.disabled")
            }
            sx={{
              height: 22,
              fontSize: 11,
              bgcolor: isEnabled ? "success.main" : "grey.400",
              color: "common.white",
            }}
          />
        </Stack>

        <Typography variant="body2" color="text.secondary" mb={2}>
          {t("p.admin.security.tfaBody")}
        </Typography>

        {!isEnabled && !setupData && (
          <Button
            variant="contained"
            startIcon={<Smartphone size={18} />}
            onClick={() => setupMut.mutate()}
          >
            {t("p.admin.security.enable")}
          </Button>
        )}

        {isEnabled && (
          <Button variant="outlined" color="error" onClick={() => setDisableDialog(true)}>
            {t("p.admin.security.disable")}
          </Button>
        )}
      </Paper>

      {/* Setup flow */}
      {setupData && (
        <Paper variant="outlined" sx={{ p: 3, mb: 2 }}>
          <Typography variant="h6" mb={2}>
            {t("p.admin.security.setupTitle")}
          </Typography>
          <Alert severity="info" sx={{ mb: 2 }}>
            {t("p.admin.security.step1")}
            <br />
            {t("p.admin.security.step2")}
            <br />
            {t("p.admin.security.step3")}
          </Alert>

          <Stack spacing={2}>
            <Box>
              <Typography variant="subtitle2" mb={1}>
                {t("p.admin.security.manualCode")}
              </Typography>
              <Paper
                variant="outlined"
                sx={{
                  p: 1.5,
                  fontFamily: "monospace",
                  wordBreak: "break-all",
                  bgcolor: "action.hover",
                  fontSize: 14,
                }}
              >
                {setupData.secret}
              </Paper>
            </Box>
            <Box sx={{ display: "flex", justifyContent: "center" }}>
              <Paper
                variant="outlined"
                sx={{ p: 2, bgcolor: "common.white", display: "inline-block" }}
              >
                <QRCodeSVG value={setupData.otpauth_uri || ""} size={180} level="M" />
              </Paper>
            </Box>
            <Box>
              <Typography variant="subtitle2" mb={1}>
                {t("p.admin.security.manualUri")}
              </Typography>
              <Paper
                variant="outlined"
                sx={{
                  p: 1.5,
                  fontFamily: "monospace",
                  wordBreak: "break-all",
                  bgcolor: "action.hover",
                  fontSize: 12,
                }}
              >
                {setupData.otpauth_uri}
              </Paper>
            </Box>
            <TextField
              label={t("p.admin.security.codeLabel")}
              value={confirmCode}
              onChange={(e) =>
                setConfirmCode(e.target.value.replace(/\D/g, "").slice(0, 6))
              }
              fullWidth
              size="small"
              placeholder="123456"
            />
            <Stack direction="row" spacing={1}>
              <Button
                variant="contained"
                onClick={() => confirmMut.mutate(confirmCode)}
                disabled={confirmCode.length !== 6 || confirmMut.isPending}
              >
                {t("common.confirm")}
              </Button>
              <Button
                onClick={() => {
                  setSetupData(null);
                  setConfirmCode("");
                }}
              >
                {t("common.cancel")}
              </Button>
            </Stack>
          </Stack>
        </Paper>
      )}

      {/* Backup codes display */}
      {backupCodes && (
        <Paper variant="outlined" sx={{ p: 3, mb: 2, borderColor: "warning.main" }}>
          <Stack
            direction="row"
            alignItems="center"
            justifyContent="space-between"
            mb={2}
          >
            <Typography variant="h6">{t("p.admin.security.backupTitle")}</Typography>
            <Button
              size="small"
              startIcon={copied ? <Check size={16} /> : <Copy size={16} />}
              onClick={copyBackupCodes}
              color={copied ? "success" : "primary"}
            >
              {copied ? t("p.admin.security.copiedAll") : t("p.admin.security.copyAll")}
            </Button>
          </Stack>
          <Alert severity="warning" sx={{ mb: 2 }}>
            {t("p.admin.security.backupWarning")}
          </Alert>
          <Paper variant="outlined" sx={{ p: 2, bgcolor: "action.hover" }}>
            <Stack direction="row" flexWrap="wrap" gap={1}>
              {backupCodes.map((code, i) => (
                <Chip key={i} label={code} sx={{ fontFamily: "monospace", m: 0.5 }} />
              ))}
            </Stack>
          </Paper>
          <Button sx={{ mt: 2 }} onClick={() => setBackupCodes(null)}>
            {t("p.admin.security.savedCodes")}
          </Button>
        </Paper>
      )}

      {/* Dispositivos sincronizados */}
      <Paper variant="outlined" sx={{ p: 3, mb: 2 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <MonitorSmartphone size={20} style={{ color: theme.palette.primary.main }} />
            <Typography variant="h6">{t("p.admin.security.devicesTitle")}</Typography>
          </Stack>
          {(devices?.length ?? 0) > 1 && (
            <Button
              size="small"
              color="error"
              variant="outlined"
              disabled={revokeAllMut.isPending}
              onClick={async () => {
                if (await confirm(t("p.admin.security.confirmRevokeAll")))
                  revokeAllMut.mutate();
              }}
            >
              {t("p.admin.security.revokeAll")}
            </Button>
          )}
        </Stack>
        <Typography variant="body2" color="text.secondary" mb={2}>
          {t("p.admin.security.devicesBody")}
        </Typography>
        {(devices ?? []).length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {t("p.admin.security.noDevices")}
          </Typography>
        ) : (
          <List dense>
            {(devices ?? []).map((d, i) => (
              <Box key={d.id}>
                {i > 0 && <Divider component="li" />}
                <ListItem
                  secondaryAction={
                    <Stack direction="row" spacing={0.5}>
                      {d.is_active && (
                        <Button
                          size="small"
                          color="warning"
                          disabled={revokeMut.isPending}
                          onClick={() => revokeMut.mutate(d.device_id)}
                        >
                          {t("p.admin.security.revoke")}
                        </Button>
                      )}
                      <Button
                        size="small"
                        color="error"
                        startIcon={<Trash2 size={13} />}
                        disabled={removeMut.isPending}
                        onClick={async () => {
                          if (
                            await confirm(
                              t("p.admin.security.confirmRemoveDevice", {
                                name: d.device_name || d.device_id,
                              }),
                            )
                          )
                            removeMut.mutate(d.device_id);
                        }}
                      >
                        {t("common.delete")}
                      </Button>
                    </Stack>
                  }
                >
                  <ListItemText
                    primary={d.device_name || d.device_id}
                    secondary={
                      d.last_sync_at
                        ? t("p.admin.security.lastSync", {
                            when: formatRelative(d.last_sync_at),
                          })
                        : t("p.admin.security.neverSynced")
                    }
                  />
                  <Chip
                    size="small"
                    sx={{ mr: 1 }}
                    label={
                      d.is_active
                        ? t("p.admin.security.deviceActive")
                        : t("p.admin.security.deviceRevokedLabel")
                    }
                    color={d.is_active ? "success" : "default"}
                    variant="outlined"
                  />
                </ListItem>
              </Box>
            ))}
          </List>
        )}
      </Paper>

      {/* Security tips */}
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Typography variant="h6" mb={2}>
          {t("p.admin.security.tipsTitle")}
        </Typography>
        <List dense>
          <ListItem>
            <ListItemIcon>
              <Key size={18} />
            </ListItemIcon>
            <ListItemText primary={t("p.admin.security.tip1")} />
          </ListItem>
          <Divider component="li" />
          <ListItem>
            <ListItemIcon>
              <ShieldCheck size={18} />
            </ListItemIcon>
            <ListItemText primary={t("p.admin.security.tip2")} />
          </ListItem>
          <Divider component="li" />
          <ListItem>
            <ListItemIcon>
              <Smartphone size={18} />
            </ListItemIcon>
            <ListItemText primary={t("p.admin.security.tip3")} />
          </ListItem>
        </List>
      </Paper>

      {/* Disable dialog */}
      <Dialog
        open={disableDialog}
        onClose={() => setDisableDialog(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>{t("p.admin.security.disable")}</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            {t("p.admin.security.disableWarning")}
          </Alert>
          <TextField
            label={t("p.admin.security.codeLabelShort")}
            value={disableCode}
            onChange={(e) =>
              setDisableCode(e.target.value.replace(/\D/g, "").slice(0, 6))
            }
            fullWidth
            size="small"
            placeholder="123456"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDisableDialog(false)}>{t("common.cancel")}</Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => disableMut.mutate(disableCode)}
            disabled={disableCode.length < 6 || disableMut.isPending}
          >
            {t("p.admin.security.disableAction")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
