import { formatDateTime } from "../lib/dates";
import { useState } from "react";
import {
  Box,
  Typography,
  Button,
  Paper,
  Stack,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  CircularProgress,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Collapse,
  MenuItem,
  useTheme,
} from "@mui/material";
import { Key, Lock, Share2, Plus, Unlock, Upload } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { encryptionApi, tasksApi } from "../api/resources";
import type { EncryptedTaskItem } from "../types";
import { notify } from "../notify";
import {
  generateRsaKeyPair,
  exportPublicKeyB64,
  exportPrivateKeyB64,
  importPrivateKeyB64,
  pemToB64,
  b64ToPem,
  loadPrivateKeyB64,
  storePrivateKey,
  generateAesKey,
  encryptJson,
  decryptJson,
  wrapAesKey,
  unwrapAesKey,
  importPublicKeyB64,
} from "../lib/e2ee";
import { authApi } from "../api/auth";
import { useTranslation } from "react-i18next";

interface SharedTaskItem extends Omit<EncryptedTaskItem, "shared_by"> {
  iv?: string;
  auth_tag?: string;
  algorithm?: string;
  encrypted_key?: string;
  shared_by?: string | number;
}

interface TaskPayload {
  title: string;
  description: string;
}

export default function EncryptionPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();

  // --- Key registration ---
  const [pemKey, setPemKey] = useState("");
  const [keyId, setKeyId] = useState("");
  const [advancedKey, setAdvancedKey] = useState(false);
  const [restoreKey, setRestoreKey] = useState("");
  const [restoreOpen, setRestoreOpen] = useState(false);
  const [hasPrivateKey, setHasPrivateKey] = useState(() => !!loadPrivateKeyB64());

  // --- Create encrypted task (plaintext → se cifra en cliente) ---
  const [createOpen, setCreateOpen] = useState(false);
  const [taskForm, setTaskForm] = useState({ title: "", description: "" });
  const [creating, setCreating] = useState(false);

  // --- Share task ---
  const [shareOpen, setShareOpen] = useState(false);
  const [shareForm, setShareForm] = useState({ taskId: "", userEmail: "" });
  const [sharing, setSharing] = useState(false);

  // --- Decrypted view ---
  const [decrypted, setDecrypted] = useState<{ id: number; payload: TaskPayload } | null>(
    null,
  );

  const { data: activeKey, isLoading: keyLoading } = useQuery({
    queryKey: ["encryption-active-key"],
    queryFn: encryptionApi.getActiveKey,
    retry: false,
  });

  const { data: encTasks, isLoading: tasksLoading } = useQuery({
    queryKey: ["encrypted-tasks"],
    queryFn: encryptionApi.listEncryptedTasks,
  });

  const { data: sharedTasks, isLoading: sharedLoading } = useQuery({
    queryKey: ["shared-encrypted-tasks"],
    queryFn: encryptionApi.sharedTasks,
  });

  const registerKeyMut = useMutation({
    mutationFn: ({
      publicKey,
      kId,
      algorithm,
    }: {
      publicKey: string;
      kId: string;
      algorithm: string;
    }) => encryptionApi.registerPublicKey(publicKey, kId, algorithm),
    onSuccess: () => {
      notify.success(t("p.shell.encryption.keyRegistered"));
      qc.invalidateQueries({ queryKey: ["encryption-active-key"] });
    },
  });

  const shareMut = useMutation({
    mutationFn: ({
      taskId,
      userEmail,
      encryptedKey,
      publicKeyId,
    }: {
      taskId: number;
      userEmail: string;
      encryptedKey: string;
      publicKeyId: number;
    }) => encryptionApi.shareTask(taskId, userEmail, encryptedKey, publicKeyId),
    onSuccess: () => {
      notify.success(t("p.shell.encryption.taskShared"));
      qc.invalidateQueries({ queryKey: ["shared-encrypted-tasks"] });
      setShareOpen(false);
    },
  });

  // --- Generar par RSA en el navegador y registrar la pública ---
  const handleGenerateKey = async () => {
    try {
      const pair = await generateRsaKeyPair();
      const pubB64 = await exportPublicKeyB64(pair.publicKey);
      const privB64 = await exportPrivateKeyB64(pair.privateKey);
      const id = `web-${Date.now().toString(36)}`;
      await registerKeyMut.mutateAsync({
        publicKey: pubB64,
        kId: id,
        algorithm: "RSA-OA-256",
      });
      storePrivateKey(privB64);
      setHasPrivateKey(true);
      // Copia de respaldo descargable: sin ella, otro navegador no descifra
      const blob = new Blob([b64ToPem(privB64, "PRIVATE KEY")], { type: "text/plain" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "todolist-private-key.pem";
      a.click();
      URL.revokeObjectURL(a.href);
      notify.success(t("p.shell.encryption.keyPairGenerated"));
    } catch {
      notify.error(t("p.shell.encryption.errorGenerateKeys"));
    }
  };

  const handleRegisterKey = () => {
    if (!pemKey || !keyId) return;
    registerKeyMut.mutate({
      publicKey: pemKey.includes("BEGIN") ? pemToB64(pemKey) : pemKey.trim(),
      kId: keyId,
      algorithm: "RSA-OA-256",
    });
  };

  const handleRestoreKey = async () => {
    const b64 = restoreKey.includes("BEGIN") ? pemToB64(restoreKey) : restoreKey.trim();
    try {
      await importPrivateKeyB64(b64);
      storePrivateKey(b64);
      setHasPrivateKey(true);
      setRestoreOpen(false);
      setRestoreKey("");
      notify.success(t("p.shell.encryption.keyRestored"));
    } catch {
      notify.error(t("p.shell.encryption.errorInvalidKey"));
    }
  };

  // --- Crear tarea cifrada: AES-256-GCM + wrap RSA + self-share ---
  const handleCreateTask = async () => {
    if (!taskForm.title.trim()) return;
    if (!activeKey || !hasPrivateKey) {
      notify.warning(t("p.shell.encryption.needKeyPair"));
      return;
    }
    setCreating(true);
    try {
      // La Task vinculada lleva un título genérico: el contenido real va cifrado
      const task = await tasksApi.create({ title: "🔒" });
      const aes = await generateAesKey();
      const enc = await encryptJson(aes, {
        title: taskForm.title.trim(),
        description: taskForm.description,
      });
      const pubB64 = activeKey.public_key?.includes("BEGIN")
        ? pemToB64(activeKey.public_key)
        : activeKey.public_key;
      const wrapped = await wrapAesKey(aes, await importPublicKeyB64(pubB64));
      const created = await encryptionApi.createEncryptedTask({
        task: task.id,
        encrypted_data: enc.encrypted_data,
        iv: enc.iv,
        auth_tag: enc.auth_tag,
        encryption_key_id: activeKey.key_id,
        algorithm: "AES-256-GCM",
      });
      // Self-share: la clave AES envuelta con la propia pública es la única
      // forma de recuperar el contenido después (el servidor no la tiene)
      const me = await authApi.me();
      await encryptionApi.shareTask(created.id, me.email, wrapped, activeKey.id);
      notify.success(t("p.shell.encryption.taskCreated"));
      qc.invalidateQueries({ queryKey: ["encrypted-tasks"] });
      qc.invalidateQueries({ queryKey: ["shared-encrypted-tasks"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setCreateOpen(false);
      setTaskForm({ title: "", description: "" });
    } catch {
      notify.error(t("p.shell.encryption.errorCreateTask"));
    } finally {
      setCreating(false);
    }
  };

  // --- Descifrar (tareas propias → self-share; compartidas → share) ---
  const handleDecrypt = async (item: SharedTaskItem) => {
    const skB64 = loadPrivateKeyB64();
    if (!skB64) {
      notify.warning(t("p.shell.encryption.noPrivateKey"));
      return;
    }
    try {
      const sk = await importPrivateKeyB64(skB64);
      const share =
        (sharedList as SharedTaskItem[]).find(
          (s) => s.id === item.id && s.encrypted_key,
        ) ?? (item.encrypted_key ? item : undefined);
      if (!share) {
        notify.error(t("p.shell.encryption.noKeyShare"));
        return;
      }
      const aes = await unwrapAesKey(share.encrypted_key!, sk);
      const payload = await decryptJson<TaskPayload>(aes, {
        encrypted_data: (item.encrypted_data ||
          item.encryptedData ||
          share.encrypted_data)!,
        iv: (item.iv ?? share.iv)!,
        auth_tag: (item.auth_tag ?? share.auth_tag)!,
      });
      setDecrypted({ id: item.id, payload });
    } catch {
      notify.error(t("p.shell.encryption.errorDecrypt"));
    }
  };

  // --- Compartir: lookup de la pública del destinatario + re-wrap ---
  const handleShare = async () => {
    if (!shareForm.taskId || !shareForm.userEmail) return;
    const skB64 = loadPrivateKeyB64();
    if (!skB64) {
      notify.warning(t("p.shell.encryption.needPrivateForShare"));
      return;
    }
    setSharing(true);
    try {
      const targetKey = await encryptionApi.lookupPublicKey(shareForm.userEmail);
      const myShare = (sharedList as SharedTaskItem[]).find(
        (s) => s.id === Number(shareForm.taskId) && s.encrypted_key,
      );
      if (!myShare) {
        notify.error(t("p.shell.encryption.missingShare"));
        return;
      }
      const sk = await importPrivateKeyB64(skB64);
      const aes = await unwrapAesKey(myShare.encrypted_key!, sk);
      const targetPubB64 = targetKey.public_key.includes("BEGIN")
        ? pemToB64(targetKey.public_key)
        : targetKey.public_key;
      const wrapped = await wrapAesKey(aes, await importPublicKeyB64(targetPubB64));
      await shareMut.mutateAsync({
        taskId: Number(shareForm.taskId),
        userEmail: shareForm.userEmail,
        encryptedKey: wrapped,
        publicKeyId: targetKey.id,
      });
    } catch (e) {
      const err = e as { response?: { status?: number; data?: { error?: string } } };
      notify.error(err.response?.data?.error ?? t("p.shell.encryption.errorShare"));
    } finally {
      setSharing(false);
    }
  };

  const taskList: EncryptedTaskItem[] =
    (encTasks as { results?: EncryptedTaskItem[] } | undefined)?.results ??
    (encTasks as EncryptedTaskItem[] | undefined) ??
    [];
  const sharedList: SharedTaskItem[] =
    (sharedTasks as { results?: SharedTaskItem[] } | undefined)?.results ??
    (sharedTasks as SharedTaskItem[] | undefined) ??
    [];

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" spacing={1} mb={3}>
        <Lock size={24} style={{ color: theme.palette.primary.main }} />
        <Typography variant="h5" fontWeight={700}>
          {t("p.shell.encryption")}
        </Typography>
      </Stack>

      <Alert severity="info" sx={{ mb: 3 }}>
        {t("p.shell.encryption.infoAlert")}
      </Alert>

      <Stack spacing={3}>
        {/* ===================== 1. Mi clave ===================== */}
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack direction="row" alignItems="center" spacing={1} mb={2}>
            <Key size={20} style={{ color: theme.palette.primary.main }} />
            <Typography variant="subtitle1" fontWeight={600}>
              {t("p.shell.encryption.myKey")}
            </Typography>
          </Stack>

          {keyLoading ? (
            <Box display="flex" justifyContent="center" py={2}>
              <CircularProgress size={24} />
            </Box>
          ) : activeKey ? (
            <Stack direction="row" spacing={1} alignItems="center" mb={2} flexWrap="wrap">
              <Chip
                size="small"
                color="success"
                label={t("p.shell.encryption.keyRegistered")}
              />
              <Chip
                size="small"
                color={hasPrivateKey ? "success" : "warning"}
                label={
                  hasPrivateKey
                    ? t("p.shell.encryption.privateKeyPresent")
                    : t("p.shell.encryption.privateKeyMissing")
                }
              />
              <Typography variant="caption" color="text.secondary">
                {activeKey.algorithm || activeKey.key_type || "RSA-OA-256"}
              </Typography>
            </Stack>
          ) : (
            <Typography color="text.secondary" variant="body2" mb={2}>
              {t("p.shell.encryption.noKey")}
            </Typography>
          )}

          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Button
              variant="contained"
              startIcon={<Key size={16} />}
              onClick={() => void handleGenerateKey()}
              disabled={registerKeyMut.isPending}
            >
              {activeKey
                ? t("p.shell.encryption.regenerateKeys")
                : t("p.shell.encryption.generateKeys")}
            </Button>
            <Button
              variant="outlined"
              startIcon={<Upload size={16} />}
              onClick={() => setRestoreOpen(true)}
            >
              {t("p.shell.encryption.restoreKey")}
            </Button>
            <Button
              variant="text"
              size="small"
              onClick={() => setAdvancedKey(!advancedKey)}
            >
              {advancedKey
                ? t("p.shell.encryption.hideAdvanced")
                : t("p.shell.encryption.showAdvanced")}
            </Button>
          </Stack>
          {activeKey && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              {t("p.shell.encryption.regenerateWarning")}
            </Alert>
          )}

          <Collapse in={advancedKey}>
            <Box mt={2}>
              <Stack spacing={2}>
                <TextField
                  label={t("p.shell.encryption.publicKeyLabel")}
                  value={pemKey}
                  onChange={(e) => setPemKey(e.target.value)}
                  multiline
                  minRows={4}
                  fullWidth
                  size="small"
                  sx={{ fontFamily: "monospace" }}
                  placeholder="-----BEGIN PUBLIC KEY-----&#10;...&#10;-----END PUBLIC KEY-----"
                />
                <TextField
                  label="Key ID"
                  value={keyId}
                  onChange={(e) => setKeyId(e.target.value)}
                  size="small"
                  helperText={t("p.shell.encryption.keyIdHelp")}
                />
                <Button
                  variant="outlined"
                  startIcon={<Key size={16} />}
                  onClick={handleRegisterKey}
                  disabled={!pemKey || !keyId || registerKeyMut.isPending}
                  sx={{ alignSelf: "flex-start" }}
                >
                  {t("p.shell.encryption.registerKey")}
                </Button>
              </Stack>
            </Box>
          </Collapse>
        </Paper>

        {/* ===================== 2. Tareas cifradas ===================== */}
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack
            direction="row"
            alignItems="center"
            justifyContent="space-between"
            mb={2}
          >
            <Stack direction="row" alignItems="center" spacing={1}>
              <Lock size={20} style={{ color: theme.palette.primary.main }} />
              <Typography variant="subtitle1" fontWeight={600}>
                {t("p.shell.encryption.encryptedTasks")}
              </Typography>
            </Stack>
            <Button
              variant="contained"
              size="small"
              startIcon={<Plus size={16} />}
              onClick={() => {
                setTaskForm({ title: "", description: "" });
                setCreateOpen(true);
              }}
            >
              {t("p.shell.encryption.new")}
            </Button>
          </Stack>

          {tasksLoading ? (
            <Box display="flex" justifyContent="center" py={3}>
              <CircularProgress size={24} />
            </Box>
          ) : taskList.length === 0 ? (
            <Typography
              color="text.secondary"
              variant="body2"
              sx={{ textAlign: "center", py: 3 }}
            >
              {t("p.shell.encryption.noEncryptedTasks")}
            </Typography>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>ID</TableCell>
                    <TableCell>{t("p.shell.encryption.colData")}</TableCell>
                    <TableCell>{t("p.shell.encryption.colCreated")}</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {taskList.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          #{item.id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography
                          variant="caption"
                          fontFamily="monospace"
                          sx={{
                            maxWidth: 380,
                            display: "block",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {item.encrypted_data || item.encryptedData}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {item.created_at ? formatDateTime(item.created_at) : "—"}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          startIcon={<Unlock size={14} />}
                          onClick={() => void handleDecrypt(item)}
                        >
                          {t("p.shell.encryption.decrypt")}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>

        {/* ===================== 3. Compartidas conmigo ===================== */}
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack
            direction="row"
            alignItems="center"
            justifyContent="space-between"
            mb={2}
          >
            <Stack direction="row" alignItems="center" spacing={1}>
              <Share2 size={20} style={{ color: theme.palette.primary.main }} />
              <Typography variant="subtitle1" fontWeight={600}>
                {t("p.shell.encryption.sharedWithMe")}
              </Typography>
            </Stack>
            <Button
              variant="outlined"
              size="small"
              startIcon={<Share2 size={16} />}
              onClick={() => {
                setShareForm({ taskId: "", userEmail: "" });
                setShareOpen(true);
              }}
            >
              {t("p.shell.encryption.shareTask")}
            </Button>
          </Stack>

          {sharedLoading ? (
            <Box display="flex" justifyContent="center" py={3}>
              <CircularProgress size={24} />
            </Box>
          ) : sharedList.length === 0 ? (
            <Typography
              color="text.secondary"
              variant="body2"
              sx={{ textAlign: "center", py: 3 }}
            >
              {t("p.shell.encryption.noSharedTasks")}
            </Typography>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>ID</TableCell>
                    <TableCell>{t("p.shell.encryption.colFrom")}</TableCell>
                    <TableCell>{t("p.shell.encryption.colData")}</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {sharedList.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          #{item.id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {item.shared_by_display ||
                            item.shared_by_email ||
                            item.shared_by ||
                            "—"}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography
                          variant="caption"
                          fontFamily="monospace"
                          sx={{
                            maxWidth: 330,
                            display: "block",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {item.encrypted_data || item.encryptedData}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          startIcon={<Unlock size={14} />}
                          onClick={() => void handleDecrypt(item)}
                        >
                          {t("p.shell.encryption.decrypt")}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>
      </Stack>

      {/* ===================== Dialog: Crear tarea cifrada ===================== */}
      <Dialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.shell.encryption.createTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("p.shell.encryption.fieldTitle")}
              value={taskForm.title}
              onChange={(e) => setTaskForm({ ...taskForm, title: e.target.value })}
              fullWidth
              size="small"
              autoFocus
            />
            <TextField
              label={t("p.shell.encryption.fieldDescription")}
              value={taskForm.description}
              onChange={(e) => setTaskForm({ ...taskForm, description: e.target.value })}
              multiline
              minRows={3}
              fullWidth
              size="small"
            />
            <Alert severity="info">{t("p.shell.encryption.createAlert")}</Alert>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => void handleCreateTask()}
            disabled={!taskForm.title.trim() || creating || !activeKey}
          >
            {creating ? (
              <CircularProgress size={18} />
            ) : (
              t("p.shell.encryption.encryptAndCreate")
            )}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===================== Dialog: Compartir tarea ===================== */}
      <Dialog
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.shell.encryption.shareTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("p.shell.encryption.shareTaskLabel")}
              value={shareForm.taskId}
              onChange={(e) => setShareForm({ ...shareForm, taskId: e.target.value })}
              fullWidth
              size="small"
              select={taskList.length > 0}
              helperText={t("p.shell.encryption.shareTaskHelp")}
            >
              {taskList.map((t) => (
                <MenuItem key={t.id} value={String(t.id)}>
                  #{t.id}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label={t("p.shell.encryption.shareEmailLabel")}
              value={shareForm.userEmail}
              onChange={(e) => setShareForm({ ...shareForm, userEmail: e.target.value })}
              fullWidth
              size="small"
              helperText={t("p.shell.encryption.shareEmailHelp")}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShareOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => void handleShare()}
            disabled={!shareForm.taskId || !shareForm.userEmail || sharing}
          >
            {sharing ? <CircularProgress size={18} /> : t("p.shell.encryption.share")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===================== Dialog: Restaurar clave privada ===================== */}
      <Dialog
        open={restoreOpen}
        onClose={() => setRestoreOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.shell.encryption.restoreKey")}</DialogTitle>
        <DialogContent>
          <TextField
            value={restoreKey}
            onChange={(e) => setRestoreKey(e.target.value)}
            multiline
            minRows={6}
            fullWidth
            size="small"
            sx={{ mt: 1, fontFamily: "monospace" }}
            placeholder="-----BEGIN PRIVATE KEY-----&#10;...&#10;-----END PRIVATE KEY-----"
            helperText={t("p.shell.encryption.restoreHelp")}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRestoreOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => void handleRestoreKey()}
            disabled={!restoreKey.trim()}
          >
            {t("p.shell.encryption.restore")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===================== Dialog: contenido descifrado ===================== */}
      <Dialog
        open={!!decrypted}
        onClose={() => setDecrypted(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          <Stack direction="row" spacing={1} alignItems="center">
            <Unlock size={18} />
            {t("p.shell.encryption.taskNumber", { id: decrypted?.id })}
          </Stack>
        </DialogTitle>
        <DialogContent>
          {decrypted && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <TextField
                label={t("p.shell.encryption.fieldTitle")}
                value={decrypted.payload.title}
                InputProps={{ readOnly: true }}
                fullWidth
                size="small"
              />
              <TextField
                label={t("p.shell.encryption.fieldDescription")}
                value={decrypted.payload.description}
                InputProps={{ readOnly: true }}
                multiline
                minRows={3}
                fullWidth
                size="small"
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDecrypted(null)}>{t("common.close")}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
