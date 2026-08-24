import { useState } from "react";
import {
  Box,
  Typography,
  Button,
  Paper,
  Stack,
  Chip,
  TextField,
  CircularProgress,
  Alert,
  Divider,
} from "@mui/material";
import { RefreshCw, Smartphone, Upload, Download } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { offlineSyncApi } from "../api/resources";
import { notify } from "../notify";

export default function OfflineSyncPage() {
  // --- Device registration ---
  const [deviceName, setDeviceName] = useState("");
  const [registeredDevice, setRegisteredDevice] = useState<any>(null);

  // --- Push ---
  const [pushText, setPushText] = useState('[\n  {"op": "create", "entity": "task", "data": {}}\n]');

  // --- Pull ---
  const [pullSince, setPullSince] = useState("");
  const [pullResult, setPullResult] = useState<any>(null);

  // --- Status ---
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [devices, setDevices] = useState<any[]>([]);

  const registerMut = useMutation({
    mutationFn: ({ deviceId, deviceName }: { deviceId: string; deviceName: string }) =>
      offlineSyncApi.registerDevice(deviceId, deviceName),
    onSuccess: (data) => {
      notify.success("Dispositivo registrado");
      setRegisteredDevice(data);
    },
  });

  const pushMut = useMutation({
    mutationFn: (operations: any[]) => offlineSyncApi.push(operations),
    onSuccess: (data) => {
      notify.success("Operaciones enviadas");
      const now = new Date().toISOString();
      setLastSync(now);
      const resp = data as any;
      if (resp?.devices) setDevices(resp.devices);
      if (resp?.accepted !== undefined || resp?.applied !== undefined) {
        // keep response available for display
      }
    },
  });

  const pullMut = useMutation({
    mutationFn: (since: string) => offlineSyncApi.pull(since),
    onSuccess: (data) => {
      notify.success("Cambios recibidos");
      setPullResult(data);
      setLastSync(new Date().toISOString());
    },
  });

  const handleRegister = () => {
    if (!deviceName) return;
    const deviceId = `dev-${Date.now()}`;
    registerMut.mutate({ deviceId, deviceName });
  };

  const handlePush = () => {
    let ops: any[];
    try {
      ops = JSON.parse(pushText);
      if (!Array.isArray(ops)) throw new Error("Debe ser un array");
    } catch (e: any) {
      notify.error(`JSON inválido: ${e.message}`);
      return;
    }
    pushMut.mutate(ops);
  };

  const handlePull = () => {
    const since = pullSince || "2000-01-01T00:00:00Z";
    pullMut.mutate(since);
  };

  const pullChanges = (pullResult as any)?.changes ?? (pullResult as any)?.results ?? [];
  const pullCount = Array.isArray(pullChanges) ? pullChanges.length : 0;

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" spacing={1} mb={3}>
        <RefreshCw size={24} color="#1976d2" />
        <Typography variant="h5" fontWeight={700}>Sincronización Offline</Typography>
      </Stack>

      {/* Sync status indicator */}
      <Alert
        severity={lastSync ? "success" : "info"}
        sx={{ mb: 3 }}
        icon={<RefreshCw size={18} />}
      >
        {lastSync ? (
          <>Última sincronización: {new Date(lastSync).toLocaleString("es-ES")}</>
        ) : (
          <>No se ha sincronizado todavía.</>
        )}
      </Alert>

      <Stack spacing={3}>
        {/* ===================== Register device ===================== */}
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack direction="row" alignItems="center" spacing={1} mb={2}>
            <Smartphone size={20} color="#1976d2" />
            <Typography variant="subtitle1" fontWeight={600}>Registrar dispositivo</Typography>
          </Stack>
          <Stack direction="row" spacing={2} alignItems="flex-start">
            <TextField
              label="Nombre del dispositivo"
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
              size="small"
              fullWidth
              placeholder="p. ej. iPhone de Alex"
            />
            <Button
              variant="contained"
              startIcon={<Smartphone size={16} />}
              onClick={handleRegister}
              disabled={!deviceName || registerMut.isPending}
            >
              Registrar
            </Button>
          </Stack>
          {registeredDevice && (
            <Box mt={2}>
              <Chip
                size="small"
                color="success"
                label={`Registrado: ${registeredDevice.device_id || registeredDevice.device_name || "OK"}`}
              />
            </Box>
          )}
        </Paper>

        {/* ===================== Push ===================== */}
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack direction="row" alignItems="center" spacing={1} mb={2}>
            <Upload size={20} color="#1976d2" />
            <Typography variant="subtitle1" fontWeight={600}>Enviar operaciones (Push)</Typography>
          </Stack>
          <TextField
            value={pushText}
            onChange={(e) => setPushText(e.target.value)}
            multiline
            minRows={5}
            fullWidth
            size="small"
            sx={{ fontFamily: "monospace" }}
            placeholder='[{"op": "create", "entity": "task", "data": {...}}]'
          />
          <Box mt={1}>
            <Button
              variant="contained"
              startIcon={<Upload size={16} />}
              onClick={handlePush}
              disabled={pushMut.isPending}
            >
              Enviar
            </Button>
          </Box>
          {pushMut.data && (
            <Box mt={2}>
              <Typography variant="caption" color="text.secondary">
                Respuesta:
              </Typography>
              <Paper variant="outlined" sx={{ p: 1, mt: 0.5, fontFamily: "monospace", fontSize: 12, bgcolor: "action.hover", overflowX: "auto" }}>
                {JSON.stringify(pushMut.data, null, 2)}
              </Paper>
            </Box>
          )}
        </Paper>

        {/* ===================== Pull ===================== */}
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack direction="row" alignItems="center" spacing={1} mb={2}>
            <Download size={20} color="#1976d2" />
            <Typography variant="subtitle1" fontWeight={600}>Recibir cambios (Pull)</Typography>
          </Stack>
          <Stack direction="row" spacing={2} alignItems="flex-start">
            <TextField
              label="Desde (ISO date)"
              value={pullSince}
              onChange={(e) => setPullSince(e.target.value)}
              size="small"
              fullWidth
              placeholder="2024-01-01T00:00:00Z (vacío = todo)"
            />
            <Button
              variant="contained"
              startIcon={<Download size={16} />}
              onClick={handlePull}
              disabled={pullMut.isPending}
            >
              Recibir
            </Button>
          </Stack>
          {pullMut.isPending ? (
            <Box display="flex" justifyContent="center" py={3}>
              <CircularProgress size={24} />
            </Box>
          ) : pullResult ? (
            <Box mt={2}>
              <Typography variant="body2" fontWeight={600} gutterBottom>
                {pullCount} cambio(s) recibido(s):
              </Typography>
              {pullCount === 0 ? (
                <Typography color="text.secondary" variant="body2">
                  No hay cambios nuevos.
                </Typography>
              ) : (
                <Paper variant="outlined" sx={{ p: 1, fontFamily: "monospace", fontSize: 12, bgcolor: "action.hover", maxHeight: 300, overflow: "auto" }}>
                  {JSON.stringify(pullChanges, null, 2)}
                </Paper>
              )}
            </Box>
          ) : null}
        </Paper>

        {/* ===================== Device list ===================== */}
        {devices.length > 0 && (
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Stack direction="row" alignItems="center" spacing={1} mb={2}>
              <Smartphone size={20} color="#1976d2" />
              <Typography variant="subtitle1" fontWeight={600}>Dispositivos</Typography>
            </Stack>
            <Stack spacing={1}>
              {devices.map((d: any, i: number) => (
                <Stack key={i} direction="row" alignItems="center" justifyContent="space-between">
                  <Typography variant="body2">
                    {d.device_name || d.device_id || `Dispositivo ${i + 1}`}
                  </Typography>
                  <Chip
                    size="small"
                    label={d.last_seen ? new Date(d.last_seen).toLocaleString("es-ES") : "—"}
                    variant="outlined"
                  />
                </Stack>
              ))}
            </Stack>
          </Paper>
        )}
      </Stack>

      <Divider sx={{ my: 3 }} />
      <Typography variant="caption" color="text.secondary">
        La sincronización offline permite registrar dispositivos, enviar operaciones pendientes y
        recibir cambios desde el servidor.
      </Typography>
    </Box>
  );
}
