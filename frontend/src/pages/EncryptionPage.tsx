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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from "@mui/material";
import { Key, Lock, Share2, Plus } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { encryptionApi } from "../api/resources";
import { notify } from "../notify";

export default function EncryptionPage() {
  const qc = useQueryClient();

  // --- Key registration ---
  const [pemKey, setPemKey] = useState("");
  const [keyId, setKeyId] = useState("");
  const [keyType, setKeyType] = useState("RSA-OA-256");

  // --- Create encrypted task ---
  const [createOpen, setCreateOpen] = useState(false);
  const [taskForm, setTaskForm] = useState({ encrypted_data: "", encrypted_key: "" });

  // --- Share task ---
  const [shareOpen, setShareOpen] = useState(false);
  const [shareForm, setShareForm] = useState({ taskId: "", userEmail: "", encryptedKey: "", publicKeyId: "" });

  const { data: activeKey, isLoading: keyLoading } = useQuery({
    queryKey: ["encryption-active-key"],
    queryFn: encryptionApi.getActiveKey,
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
    mutationFn: ({ publicKey, kId, algorithm }: { publicKey: string; kId: string; algorithm: string }) =>
      encryptionApi.registerPublicKey(publicKey, kId, algorithm),
    onSuccess: () => {
      notify.success("Clave pública registrada");
      qc.invalidateQueries({ queryKey: ["encryption-active-key"] });
    },
  });

  const createTaskMut = useMutation({
    mutationFn: encryptionApi.createEncryptedTask,
    onSuccess: () => {
      notify.success("Tarea cifrada creada");
      qc.invalidateQueries({ queryKey: ["encrypted-tasks"] });
      setCreateOpen(false);
    },
  });

  const shareMut = useMutation({
    mutationFn: ({ taskId, userEmail, encryptedKey, publicKeyId }: { taskId: number; userEmail: string; encryptedKey: string; publicKeyId: number }) =>
      encryptionApi.shareTask(taskId, userEmail, encryptedKey, publicKeyId),
    onSuccess: () => {
      notify.success("Tarea compartida");
      qc.invalidateQueries({ queryKey: ["shared-encrypted-tasks"] });
      setShareOpen(false);
    },
  });

  const handleRegisterKey = () => {
    if (!pemKey || !keyId) return;
    registerKeyMut.mutate({ publicKey: pemKey, kId: keyId, algorithm: keyType });
  };

  const handleCreateTask = () => {
    if (!taskForm.encrypted_data || !taskForm.encrypted_key) return;
    createTaskMut.mutate(taskForm);
  };

  const handleShare = () => {
    if (!shareForm.taskId || !shareForm.userEmail || !shareForm.encryptedKey || !shareForm.publicKeyId) return;
    shareMut.mutate({
      taskId: Number(shareForm.taskId),
      userEmail: shareForm.userEmail,
      encryptedKey: shareForm.encryptedKey,
      publicKeyId: Number(shareForm.publicKeyId),
    });
  };

  const taskList = (encTasks as any)?.results ?? (encTasks as any) ?? [];
  const sharedList = (sharedTasks as any)?.results ?? (sharedTasks as any) ?? [];

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" spacing={1} mb={3}>
        <Lock size={24} color="#1976d2" />
        <Typography variant="h5" fontWeight={700}>Cifrado E2E</Typography>
      </Stack>

      <Alert severity="info" sx={{ mb: 3 }}>
        El cifrado de extremo a extremo protege el contenido de tus tareas. Registra tu clave pública
        para que otros puedan compartir contigo, y cifra las tareas antes de enviarlas al servidor.
      </Alert>

      <Stack spacing={3}>
        {/* ===================== 1. Mi clave pública ===================== */}
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack direction="row" alignItems="center" spacing={1} mb={2}>
            <Key size={20} color="#1976d2" />
            <Typography variant="subtitle1" fontWeight={600}>Mi clave pública</Typography>
          </Stack>

          {keyLoading ? (
            <Box display="flex" justifyContent="center" py={2}>
              <CircularProgress size={24} />
            </Box>
          ) : activeKey ? (
            <Box mb={2}>
              <Stack direction="row" spacing={1} alignItems="center" mb={1}>
                <Chip size="small" color="success" label="Clave activa" />
                <Typography variant="caption" color="text.secondary">
                  {activeKey.algorithm || activeKey.key_type || "—"}
                </Typography>
              </Stack>
              <Paper variant="outlined" sx={{ p: 1, fontFamily: "monospace", fontSize: 11, bgcolor: "action.hover", maxHeight: 120, overflow: "auto", wordBreak: "break-all" }}>
                {activeKey.public_key || activeKey.publicKey || JSON.stringify(activeKey)}
              </Paper>
            </Box>
          ) : (
            <Typography color="text.secondary" variant="body2" mb={2}>
              No tienes ninguna clave pública activa.
            </Typography>
          )}

          <DividerLine />
          <Typography variant="body2" fontWeight={600} mb={1}>Registrar nueva clave</Typography>
          <Stack spacing={2}>
            <TextField
              label="Clave pública (PEM)"
              value={pemKey}
              onChange={(e) => setPemKey(e.target.value)}
              multiline
              minRows={4}
              fullWidth
              size="small"
              sx={{ fontFamily: "monospace" }}
              placeholder="-----BEGIN PUBLIC KEY-----&#10;...&#10;-----END PUBLIC KEY-----"
            />
            <Stack direction="row" spacing={2}>
              <TextField
                label="Key ID"
                value={keyId}
                onChange={(e) => setKeyId(e.target.value)}
                size="small"
                fullWidth
                helperText="Identificador único para la clave"
              />
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel>Tipo de clave</InputLabel>
                <Select
                  value={keyType}
                  label="Tipo de clave"
                  onChange={(e) => setKeyType(e.target.value)}
                >
                  <MenuItem value="RSA-OA-256">RSA (RSA-OA-256)</MenuItem>
                  <MenuItem value="X25519">X25519</MenuItem>
                </Select>
              </FormControl>
            </Stack>
            <Button
              variant="contained"
              startIcon={<Key size={16} />}
              onClick={handleRegisterKey}
              disabled={!pemKey || !keyId || registerKeyMut.isPending}
            >
              Registrar clave
            </Button>
          </Stack>
        </Paper>

        {/* ===================== 2. Tareas cifradas ===================== */}
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
            <Stack direction="row" alignItems="center" spacing={1}>
              <Lock size={20} color="#1976d2" />
              <Typography variant="subtitle1" fontWeight={600}>Tareas cifradas</Typography>
            </Stack>
            <Button
              variant="contained"
              size="small"
              startIcon={<Plus size={16} />}
              onClick={() => { setTaskForm({ encrypted_data: "", encrypted_key: "" }); setCreateOpen(true); }}
            >
              Nueva
            </Button>
          </Stack>

          {tasksLoading ? (
            <Box display="flex" justifyContent="center" py={3}>
              <CircularProgress size={24} />
            </Box>
          ) : taskList.length === 0 ? (
            <Typography color="text.secondary" variant="body2" sx={{ textAlign: "center", py: 3 }}>
              No tienes tareas cifradas.
            </Typography>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>ID</TableCell>
                    <TableCell>Datos cifrados</TableCell>
                    <TableCell>Creada</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {taskList.map((t: any) => (
                    <TableRow key={t.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>#{t.id}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" fontFamily="monospace" sx={{ maxWidth: 400, display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {t.encrypted_data || t.encryptedData}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {t.created_at ? new Date(t.created_at).toLocaleString("es-ES") : "—"}
                        </Typography>
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
          <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
            <Stack direction="row" alignItems="center" spacing={1}>
              <Share2 size={20} color="#1976d2" />
              <Typography variant="subtitle1" fontWeight={600}>Compartidas conmigo</Typography>
            </Stack>
            <Button
              variant="outlined"
              size="small"
              startIcon={<Share2 size={16} />}
              onClick={() => { setShareForm({ taskId: "", userEmail: "", encryptedKey: "", publicKeyId: "" }); setShareOpen(true); }}
            >
              Compartir tarea
            </Button>
          </Stack>

          {sharedLoading ? (
            <Box display="flex" justifyContent="center" py={3}>
              <CircularProgress size={24} />
            </Box>
          ) : sharedList.length === 0 ? (
            <Typography color="text.secondary" variant="body2" sx={{ textAlign: "center", py: 3 }}>
              No tienes tareas compartidas contigo.
            </Typography>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>ID</TableCell>
                    <TableCell>De</TableCell>
                    <TableCell>Datos cifrados</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {sharedList.map((t: any) => (
                    <TableRow key={t.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>#{t.id}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {t.shared_by_display || t.shared_by_email || `Usuario #${t.shared_by}`}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" fontFamily="monospace" sx={{ maxWidth: 350, display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {t.encrypted_data || t.encryptedData}
                        </Typography>
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
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Crear tarea cifrada</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Encrypted data"
              value={taskForm.encrypted_data}
              onChange={(e) => setTaskForm({ ...taskForm, encrypted_data: e.target.value })}
              multiline
              minRows={3}
              fullWidth
              size="small"
              sx={{ fontFamily: "monospace" }}
            />
            <TextField
              label="Encrypted key"
              value={taskForm.encrypted_key}
              onChange={(e) => setTaskForm({ ...taskForm, encrypted_key: e.target.value })}
              multiline
              minRows={2}
              fullWidth
              size="small"
              sx={{ fontFamily: "monospace" }}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancelar</Button>
          <Button variant="contained" onClick={handleCreateTask} disabled={!taskForm.encrypted_data || !taskForm.encrypted_key || createTaskMut.isPending}>
            Crear
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===================== Dialog: Compartir tarea ===================== */}
      <Dialog open={shareOpen} onClose={() => setShareOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Compartir tarea cifrada</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="ID de la tarea"
              value={shareForm.taskId}
              onChange={(e) => setShareForm({ ...shareForm, taskId: e.target.value })}
              fullWidth
              size="small"
            />
            <TextField
              label="Email del usuario"
              value={shareForm.userEmail}
              onChange={(e) => setShareForm({ ...shareForm, userEmail: e.target.value })}
              fullWidth
              size="small"
            />
            <TextField
              label="Encrypted key (para ese usuario)"
              value={shareForm.encryptedKey}
              onChange={(e) => setShareForm({ ...shareForm, encryptedKey: e.target.value })}
              multiline
              minRows={2}
              fullWidth
              size="small"
              sx={{ fontFamily: "monospace" }}
            />
            <TextField
              label="ID de la clave pública del destinatario"
              value={shareForm.publicKeyId}
              onChange={(e) => setShareForm({ ...shareForm, publicKeyId: e.target.value })}
              fullWidth
              size="small"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShareOpen(false)}>Cancelar</Button>
          <Button variant="contained" onClick={handleShare} disabled={!shareForm.taskId || !shareForm.userEmail || !shareForm.encryptedKey || !shareForm.publicKeyId || shareMut.isPending}>
            Compartir
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

function DividerLine() {
  return <Box sx={{ borderTop: 1, borderColor: "divider", my: 2 }} />;
}
