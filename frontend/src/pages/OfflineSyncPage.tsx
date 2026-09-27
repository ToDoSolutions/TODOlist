import { formatDateTime } from "../lib/dates";
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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Tooltip,
  useTheme,
} from "@mui/material";
import {
  RefreshCw,
  Smartphone,
  Upload,
  Download,
  History,
  GitCompareArrows,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { offlineSyncApi, syncOperationsApi, type ApiPayload } from "../api/resources";
import type { OfflineDevice, SyncOperationItem, PullResult } from "../types";
import { notify } from "../notify";
import { useTranslation } from "react-i18next";

export default function OfflineSyncPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();
  // --- Device registration ---
  const [deviceName, setDeviceName] = useState("");
  const [registeredDevice, setRegisteredDevice] = useState<OfflineDevice | null>(null);

  // --- Push ---
  const [pushText, setPushText] = useState(
    '[\n  {"op": "create", "entity": "task", "data": {}}\n]',
  );

  // --- Pull ---
  const [pullSince, setPullSince] = useState("");
  const [pullResult, setPullResult] = useState<PullResult | null>(null);

  // --- Status ---
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [devices, setDevices] = useState<OfflineDevice[]>([]);
  const [conflictOp, setConflictOp] = useState<SyncOperationItem | null>(null);

  const registerMut = useMutation({
    mutationFn: ({ deviceId, deviceName }: { deviceId: string; deviceName: string }) =>
      offlineSyncApi.registerDevice(deviceId, deviceName),
    onSuccess: (data) => {
      notify.success(t("p.integr.deviceRegistered"));
      setRegisteredDevice(data);
    },
  });

  const pushMut = useMutation({
    mutationFn: (operations: ApiPayload[]) => offlineSyncApi.push(operations),
    onSuccess: (data) => {
      notify.success(t("p.integr.opsSent"));
      const now = new Date().toISOString();
      setLastSync(now);
      const resp = data as PullResult;
      if (resp?.devices) setDevices(resp.devices);
      qc.invalidateQueries({ queryKey: ["sync-operations"] });
    },
  });

  const pullMut = useMutation({
    mutationFn: (since: string) => offlineSyncApi.pull(since),
    onSuccess: (data) => {
      notify.success(t("p.integr.changesReceived"));
      setPullResult(data);
      setLastSync(new Date().toISOString());
      qc.invalidateQueries({ queryKey: ["sync-operations"] });
    },
  });

  const handleRegister = () => {
    if (!deviceName) return;
    const deviceId = `dev-${Date.now()}`;
    registerMut.mutate({ deviceId, deviceName });
  };

  const {
    data: operationsData,
    isLoading: opsLoading,
    isError: opsError,
  } = useQuery({
    queryKey: ["sync-operations"],
    queryFn: syncOperationsApi.list,
  });
  const operations = operationsData || [];

  const handlePush = () => {
    let ops: ApiPayload[];
    try {
      ops = JSON.parse(pushText);
      if (!Array.isArray(ops)) throw new Error(t("p.integr.mustBeArray"));
    } catch (e) {
      notify.error(
        t("p.integr.invalidJson", {
          msg: e instanceof Error ? e.message : String(e),
        }),
      );
      return;
    }
    pushMut.mutate(ops);
  };

  const handlePull = () => {
    const since = pullSince || "2000-01-01T00:00:00Z";
    pullMut.mutate(since);
  };

  const pullChanges: SyncOperationItem[] =
    pullResult?.changes ?? pullResult?.results ?? [];
  const pullCount = Array.isArray(pullChanges) ? pullChanges.length : 0;

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" spacing={1} mb={3}>
        <RefreshCw size={24} style={{ color: theme.palette.primary.main }} />
        <Typography variant="h5" fontWeight={700}>
          {t("p.integr.syncTitle")}
        </Typography>
      </Stack>

      {/* Sync status indicator */}
      <Alert
        severity={lastSync ? "success" : "info"}
        sx={{ mb: 3 }}
        icon={<RefreshCw size={18} />}
      >
        {lastSync ? (
          <>{t("p.integr.lastSync", { date: formatDateTime(lastSync) })}</>
        ) : (
          <>{t("p.integr.notSynced")}</>
        )}
      </Alert>

      <Stack spacing={3}>
        {/* ===================== Register device ===================== */}
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack direction="row" alignItems="center" spacing={1} mb={2}>
            <Smartphone size={20} style={{ color: theme.palette.primary.main }} />
            <Typography variant="subtitle1" fontWeight={600}>
              {t("p.integr.registerDevice")}
            </Typography>
          </Stack>
          <Stack direction="row" spacing={2} alignItems="flex-start">
            <TextField
              label={t("p.integr.deviceName")}
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
              size="small"
              fullWidth
              placeholder={t("p.integr.deviceNamePh")}
            />
            <Button
              variant="contained"
              startIcon={<Smartphone size={16} />}
              onClick={handleRegister}
              disabled={!deviceName || registerMut.isPending}
            >
              {t("p.integr.register")}
            </Button>
          </Stack>
          {registeredDevice && (
            <Box mt={2}>
              <Chip
                size="small"
                color="success"
                label={t("p.integr.registered", {
                  device:
                    registeredDevice.device_id ||
                    registeredDevice.device_name ||
                    t("p.integr.ok"),
                })}
              />
            </Box>
          )}
        </Paper>

        {/* ===================== Push ===================== */}
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack direction="row" alignItems="center" spacing={1} mb={2}>
            <Upload size={20} style={{ color: theme.palette.primary.main }} />
            <Typography variant="subtitle1" fontWeight={600}>
              {t("p.integr.pushTitle")}
            </Typography>
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
              {t("p.integr.send")}
            </Button>
          </Box>
          {pushMut.data && (
            <Box mt={2}>
              <Typography variant="caption" color="text.secondary">
                {t("p.integr.response")}
              </Typography>
              <Paper
                variant="outlined"
                sx={{
                  p: 1,
                  mt: 0.5,
                  fontFamily: "monospace",
                  fontSize: 12,
                  bgcolor: "action.hover",
                  overflowX: "auto",
                }}
              >
                {JSON.stringify(pushMut.data, null, 2)}
              </Paper>
            </Box>
          )}
        </Paper>

        {/* ===================== Pull ===================== */}
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack direction="row" alignItems="center" spacing={1} mb={2}>
            <Download size={20} style={{ color: theme.palette.primary.main }} />
            <Typography variant="subtitle1" fontWeight={600}>
              {t("p.integr.pullTitle")}
            </Typography>
          </Stack>
          <Stack direction="row" spacing={2} alignItems="flex-start">
            <TextField
              label={t("p.integr.sinceLabel")}
              value={pullSince}
              onChange={(e) => setPullSince(e.target.value)}
              size="small"
              fullWidth
              placeholder={t("p.integr.sincePh")}
            />
            <Button
              variant="contained"
              startIcon={<Download size={16} />}
              onClick={handlePull}
              disabled={pullMut.isPending}
            >
              {t("p.integr.receive")}
            </Button>
          </Stack>
          {pullMut.isPending ? (
            <Box display="flex" justifyContent="center" py={3}>
              <CircularProgress size={24} />
            </Box>
          ) : pullResult ? (
            <Box mt={2}>
              <Typography variant="body2" fontWeight={600} gutterBottom>
                {t("p.integr.changesCount", { count: pullCount })}
              </Typography>
              {pullCount === 0 ? (
                <Typography color="text.secondary" variant="body2">
                  {t("p.integr.noChanges")}
                </Typography>
              ) : (
                <Paper
                  variant="outlined"
                  sx={{
                    p: 1,
                    fontFamily: "monospace",
                    fontSize: 12,
                    bgcolor: "action.hover",
                    maxHeight: 300,
                    overflow: "auto",
                  }}
                >
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
              <Smartphone size={20} style={{ color: theme.palette.primary.main }} />
              <Typography variant="subtitle1" fontWeight={600}>
                {t("p.integr.devices")}
              </Typography>
            </Stack>
            <Stack spacing={1}>
              {devices.map((d, i) => (
                <Stack
                  key={i}
                  direction="row"
                  alignItems="center"
                  justifyContent="space-between"
                >
                  <Typography variant="body2">
                    {d.device_name ||
                      d.device_id ||
                      t("p.integr.deviceFallback", { n: i + 1 })}
                  </Typography>
                  <Chip
                    size="small"
                    label={d.last_seen ? formatDateTime(d.last_seen) : "—"}
                    variant="outlined"
                  />
                </Stack>
              ))}
            </Stack>
          </Paper>
        )}
      </Stack>

      {/* ===================== Sync operations history ===================== */}
      <Box mt={4}>
        <Stack direction="row" alignItems="center" spacing={1} mb={2}>
          <History size={20} style={{ color: theme.palette.primary.main }} />
          <Typography variant="subtitle1" fontWeight={600}>
            {t("p.integr.opsHistory")}
          </Typography>
        </Stack>
        {opsLoading ? (
          <Box display="flex" justifyContent="center" py={3}>
            <CircularProgress size={24} />
          </Box>
        ) : opsError ? (
          <Alert severity="error">{t("p.integr.opsLoadError")}</Alert>
        ) : operations.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
            <Typography color="text.secondary">{t("p.integr.opsEmpty")}</Typography>
          </Paper>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t("p.integr.type")}</TableCell>
                  <TableCell>{t("p.integr.entity")}</TableCell>
                  <TableCell>{t("p.integr.entityId")}</TableCell>
                  <TableCell>{t("p.integr.status")}</TableCell>
                  <TableCell>{t("p.integr.conflict")}</TableCell>
                  <TableCell>{t("p.integr.date")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {operations.map((op: SyncOperationItem) => (
                  <TableRow key={op.id}>
                    <TableCell>
                      <Chip size="small" label={op.op_type} variant="outlined" />
                    </TableCell>
                    <TableCell>{op.entity_type}</TableCell>
                    <TableCell>{op.entity_id ?? "—"}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={op.status}
                        sx={{
                          height: 18,
                          fontSize: 10,
                          bgcolor:
                            op.status === "applied"
                              ? "success.main"
                              : op.status === "rejected"
                                ? "error.main"
                                : "warning.main",
                          color: "common.white",
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      {op.status === "conflict" ? (
                        <Tooltip title={t("p.integr.viewComparison")}>
                          <IconButton
                            size="small"
                            aria-label={t("p.integr.viewConflictAria", {
                              id: op.id,
                            })}
                            onClick={() => setConflictOp(op)}
                          >
                            <GitCompareArrows size={15} />
                          </IconButton>
                        </Tooltip>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {op.created_at ? formatDateTime(op.created_at) : "—"}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      {/* Comparación campo a campo de un conflicto */}
      <Dialog
        open={!!conflictOp}
        onClose={() => setConflictOp(null)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {t("p.integr.conflictTitle", {
            type: conflictOp?.entity_type,
            id: conflictOp?.entity_id,
          })}
        </DialogTitle>
        <DialogContent>
          {conflictOp?.conflict_data?.conflicting_fields?.length ? (
            <>
              <Typography variant="body2" color="text.secondary" mb={1.5}>
                {t("p.integr.conflictExplain")}
              </Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t("p.integr.field")}</TableCell>
                    <TableCell>{t("p.integr.baseValue")}</TableCell>
                    <TableCell>{t("p.integr.serverValue")}</TableCell>
                    <TableCell>{t("p.integr.clientValue")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {conflictOp.conflict_data.conflicting_fields.map((f) => (
                    <TableRow key={f.field}>
                      <TableCell>
                        <Typography
                          variant="body2"
                          fontWeight={600}
                          fontFamily="monospace"
                        >
                          {f.field}
                        </Typography>
                      </TableCell>
                      <TableCell>{JSON.stringify(f.base) ?? "—"}</TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {JSON.stringify(f.server) ?? "—"}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="primary">
                          {JSON.stringify(f.client) ?? "—"}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          ) : (
            <Alert severity="info">{t("p.integr.objectConflict")}</Alert>
          )}
          {conflictOp?.conflict_data?.server && (
            <Box
              component="pre"
              sx={{
                mt: 1.5,
                p: 1.5,
                bgcolor: "action.hover",
                borderRadius: 1,
                fontSize: 12,
                overflow: "auto",
                maxHeight: 300,
              }}
            >
              {JSON.stringify(conflictOp.conflict_data.server, null, 2)}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConflictOp(null)}>{t("p.integr.close")}</Button>
        </DialogActions>
      </Dialog>

      <Divider sx={{ my: 3 }} />
      <Typography variant="caption" color="text.secondary">
        {t("p.integr.syncFooter")}
      </Typography>
    </Box>
  );
}
