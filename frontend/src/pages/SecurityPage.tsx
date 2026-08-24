import { useState } from "react";
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
} from "@mui/material";
import { Shield, ShieldCheck, ShieldAlert, Key, Smartphone, Copy, Check } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { twofactorApi } from "../api/resources";
import { notify } from "../notify";

export default function SecurityPage() {
  const qc = useQueryClient();
  const [setupData, setSetupData] = useState<any>(null);
  const [confirmCode, setConfirmCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [disableDialog, setDisableDialog] = useState(false);
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: status, isLoading } = useQuery({
    queryKey: ["2fa-status"],
    queryFn: twofactorApi.status,
  });

  const setupMut = useMutation({
    mutationFn: twofactorApi.setup,
    onSuccess: (data) => setSetupData(data),
    onError: () => notify.error("Error al iniciar setup 2FA"),
  });

  const confirmMut = useMutation({
    mutationFn: twofactorApi.confirm,
    onSuccess: (data) => {
      notify.success("2FA activado correctamente");
      setSetupData(null);
      setConfirmCode("");
      setBackupCodes(data.backup_codes);
      qc.invalidateQueries({ queryKey: ["2fa-status"] });
    },
    onError: () => notify.error("Código inválido"),
  });

  const disableMut = useMutation({
    mutationFn: twofactorApi.disable,
    onSuccess: () => {
      notify.info("2FA desactivado");
      setDisableDialog(false);
      setDisableCode("");
      qc.invalidateQueries({ queryKey: ["2fa-status"] });
    },
    onError: () => notify.error("Código inválido"),
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
        <Shield size={24} color="#1976d2" />
        <Typography variant="h5" fontWeight={700}>Seguridad</Typography>
      </Stack>

      {/* 2FA Status */}
      <Paper variant="outlined" sx={{ p: 3, mb: 2 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
          <Stack direction="row" alignItems="center" spacing={1}>
            {isEnabled ? <ShieldCheck size={20} color="#43a047" /> : <ShieldAlert size={20} color="#f57c00" />}
            <Typography variant="h6">Autenticación de dos factores (2FA)</Typography>
          </Stack>
          <Chip
            size="small"
            label={isEnabled ? "Activado" : "Desactivado"}
            sx={{
              height: 22, fontSize: 11,
              bgcolor: isEnabled ? "success.main" : "grey.400",
              color: "#fff",
            }}
          />
        </Stack>

        <Typography variant="body2" color="text.secondary" mb={2}>
          Protege tu cuenta con una capa adicional de seguridad. Al activar 2FA,
          necesitarás un código de tu app autenticadora (Google Authenticator, Authy)
          además de tu contraseña para iniciar sesión.
        </Typography>

        {!isEnabled && !setupData && (
          <Button variant="contained" startIcon={<Smartphone size={18} />} onClick={() => setupMut.mutate()}>
            Activar 2FA
          </Button>
        )}

        {isEnabled && (
          <Button variant="outlined" color="error" onClick={() => setDisableDialog(true)}>
            Desactivar 2FA
          </Button>
        )}
      </Paper>

      {/* Setup flow */}
      {setupData && (
        <Paper variant="outlined" sx={{ p: 3, mb: 2 }}>
          <Typography variant="h6" mb={2}>Configurar 2FA</Typography>
          <Alert severity="info" sx={{ mb: 2 }}>
            1. Abre tu app autenticadora (Google Authenticator, Authy, etc.)<br />
            2. Escanea el QR o introduce el código manualmente<br />
            3. Introduce el código de 6 dígitos que genera la app
          </Alert>

          <Stack spacing={2}>
            <Box>
              <Typography variant="subtitle2" mb={1}>Código manual:</Typography>
              <Paper variant="outlined" sx={{ p: 1.5, fontFamily: "monospace", wordBreak: "break-all", bgcolor: "action.hover", fontSize: 14 }}>
                {setupData.secret}
              </Paper>
            </Box>
            <Box>
              <Typography variant="subtitle2" mb={1}>URI para QR:</Typography>
              <Paper variant="outlined" sx={{ p: 1.5, fontFamily: "monospace", wordBreak: "break-all", bgcolor: "action.hover", fontSize: 12 }}>
                {setupData.otpauth_uri}
              </Paper>
            </Box>
            <TextField
              label="Código de verificación (6 dígitos)"
              value={confirmCode}
              onChange={(e) => setConfirmCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
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
                Confirmar
              </Button>
              <Button onClick={() => { setSetupData(null); setConfirmCode(""); }}>
                Cancelar
              </Button>
            </Stack>
          </Stack>
        </Paper>
      )}

      {/* Backup codes display */}
      {backupCodes && (
        <Paper variant="outlined" sx={{ p: 3, mb: 2, borderColor: "warning.main" }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
            <Typography variant="h6">Códigos de backup</Typography>
            <Button
              size="small"
              startIcon={copied ? <Check size={16} /> : <Copy size={16} />}
              onClick={copyBackupCodes}
              color={copied ? "success" : "primary"}
            >
              {copied ? "Copiados" : "Copiar todos"}
            </Button>
          </Stack>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Guarda estos códigos en un lugar seguro. Cada uno se puede usar una sola vez
            si pierdes acceso a tu app autenticadora.
          </Alert>
          <Paper variant="outlined" sx={{ p: 2, bgcolor: "action.hover" }}>
            <Stack direction="row" flexWrap="wrap" gap={1}>
              {backupCodes.map((code, i) => (
                <Chip key={i} label={code} sx={{ fontFamily: "monospace", m: 0.5 }} />
              ))}
            </Stack>
          </Paper>
          <Button sx={{ mt: 2 }} onClick={() => setBackupCodes(null)}>
            He guardado los códigos
          </Button>
        </Paper>
      )}

      {/* Security tips */}
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Typography variant="h6" mb={2}>Consejos de seguridad</Typography>
        <List dense>
          <ListItem>
            <ListItemIcon><Key size={18} /></ListItemIcon>
            <ListItemText primary="Usa una contraseña única y fuerte" />
          </ListItem>
          <Divider component="li" />
          <ListItem>
            <ListItemIcon><ShieldCheck size={18} /></ListItemIcon>
            <ListItemText primary="Activa 2FA para protección adicional" />
          </ListItem>
          <Divider component="li" />
          <ListItem>
            <ListItemIcon><Smartphone size={18} /></ListItemIcon>
            <ListItemText primary="Guarda los códigos de backup offline" />
          </ListItem>
        </List>
      </Paper>

      {/* Disable dialog */}
      <Dialog open={disableDialog} onClose={() => setDisableDialog(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Desactivar 2FA</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Tu cuenta será menos segura. Introduce un código TOTP o de backup para confirmar.
          </Alert>
          <TextField
            label="Código de verificación"
            value={disableCode}
            onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            fullWidth
            size="small"
            placeholder="123456"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDisableDialog(false)}>Cancelar</Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => disableMut.mutate(disableCode)}
            disabled={disableCode.length < 6 || disableMut.isPending}
          >
            Desactivar
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
