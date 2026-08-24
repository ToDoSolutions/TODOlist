import { useState } from "react";
import {
  Box,
  Typography,
  Button,
  Paper,
  Stack,
  Chip,
  Tabs,
  Tab,
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
  IconButton,
  Tooltip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Collapse,
} from "@mui/material";
import { Users, Plus, Trash2, UserPlus, AtSign } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { collaborationApi } from "../api/resources";
import { notify } from "../notify";

export default function TeamsPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState(0);

  // --- Teams tab state ---
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ name: "", description: "" });
  const [expandedTeam, setExpandedTeam] = useState<number | null>(null);
  const [addMemberTeamId, setAddMemberTeamId] = useState<number | null>(null);
  const [memberForm, setMemberForm] = useState({ userId: "", role: "member" });

  const { data: teams, isLoading: teamsLoading } = useQuery({
    queryKey: ["teams"],
    queryFn: collaborationApi.teams.list,
  });

  const { data: mentions, isLoading: mentionsLoading } = useQuery({
    queryKey: ["mentions"],
    queryFn: collaborationApi.mentions.list,
  });

  const membersQuery = useQuery({
    queryKey: ["team-members", expandedTeam],
    queryFn: () => collaborationApi.teams.members(expandedTeam!),
    enabled: expandedTeam !== null,
  });

  const createMut = useMutation({
    mutationFn: collaborationApi.teams.create,
    onSuccess: () => {
      notify.success("Equipo creado");
      qc.invalidateQueries({ queryKey: ["teams"] });
      setCreateOpen(false);
    },
  });

  const addMemberMut = useMutation({
    mutationFn: ({ teamId, userId, role }: { teamId: number; userId: number; role: string }) =>
      collaborationApi.teams.addMember(teamId, userId, role),
    onSuccess: () => {
      notify.success("Miembro añadido");
      setAddMemberTeamId(null);
      if (expandedTeam !== null) qc.invalidateQueries({ queryKey: ["team-members", expandedTeam] });
    },
  });

  const removeMemberMut = useMutation({
    mutationFn: ({ teamId, memberId }: { teamId: number; memberId: number }) =>
      collaborationApi.teams.removeMember(teamId, memberId),
    onSuccess: () => {
      notify.info("Miembro eliminado");
      if (expandedTeam !== null) qc.invalidateQueries({ queryKey: ["team-members", expandedTeam] });
    },
  });

  const teamList = (teams as any)?.results ?? (teams as any) ?? [];
  const mentionList = (mentions as any)?.results ?? (mentions as any) ?? [];
  const memberList = (membersQuery.data as any)?.results ?? (membersQuery.data as any) ?? [];

  const handleCreate = () => {
    if (!createForm.name) return;
    createMut.mutate({ name: createForm.name, description: createForm.description });
  };

  const handleAddMember = () => {
    if (addMemberTeamId === null || !memberForm.userId) return;
    addMemberMut.mutate({
      teamId: addMemberTeamId,
      userId: Number(memberForm.userId),
      role: memberForm.role,
    });
  };

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" spacing={1} mb={3}>
        <Users size={24} color="#1976d2" />
        <Typography variant="h5" fontWeight={700}>Equipos y Menciones</Typography>
      </Stack>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab icon={<Users size={16} />} iconPosition="start" label="Equipos" />
        <Tab icon={<AtSign size={16} />} iconPosition="start" label="Menciones" />
      </Tabs>

      {/* ===================== TAB 1: Equipos ===================== */}
      {tab === 0 && (
        <Box>
          <Stack direction="row" justifyContent="flex-end" mb={2}>
            <Button
              variant="contained"
              startIcon={<Plus size={18} />}
              onClick={() => { setCreateForm({ name: "", description: "" }); setCreateOpen(true); }}
            >
              Nuevo equipo
            </Button>
          </Stack>

          {teamsLoading ? (
            <Box display="flex" justifyContent="center" py={5}>
              <CircularProgress />
            </Box>
          ) : teamList.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
              <Users size={48} color="#ccc" />
              <Typography color="text.secondary" mt={1}>
                No tienes equipos. Crea uno para empezar a colaborar.
              </Typography>
            </Paper>
          ) : (
            <Stack spacing={2}>
              {teamList.map((t: any) => (
                <Paper key={t.id} variant="outlined">
                  <Stack
                    direction="row"
                    alignItems="center"
                    justifyContent="space-between"
                    sx={{ p: 2, cursor: "pointer" }}
                    onClick={() => setExpandedTeam(expandedTeam === t.id ? null : t.id)}
                  >
                    <Stack direction="row" alignItems="center" spacing={1.5}>
                      <Users size={20} color="#1976d2" />
                      <Box>
                        <Typography variant="subtitle1" fontWeight={600}>{t.name}</Typography>
                        {t.description && (
                          <Typography variant="caption" color="text.secondary">
                            {t.description}
                          </Typography>
                        )}
                      </Box>
                    </Stack>
                    <Stack direction="row" alignItems="center" spacing={1}>
                      {typeof t.member_count === "number" && (
                        <Chip size="small" label={`${t.member_count} miembros`} variant="outlined" />
                      )}
                      <Button
                        size="small"
                        startIcon={<UserPlus size={14} />}
                        onClick={(e) => { e.stopPropagation(); setAddMemberTeamId(t.id); setMemberForm({ userId: "", role: "member" }); }}
                      >
                        Añadir
                      </Button>
                    </Stack>
                  </Stack>

                  <Collapse in={expandedTeam === t.id}>
                    <Box sx={{ p: 2, pt: 0 }}>
                      {membersQuery.isLoading ? (
                        <Box display="flex" justifyContent="center" py={2}>
                          <CircularProgress size={24} />
                        </Box>
                      ) : memberList.length === 0 ? (
                        <Typography color="text.secondary" variant="body2" sx={{ py: 1 }}>
                          Este equipo no tiene miembros.
                        </Typography>
                      ) : (
                        <TableContainer component={Paper} variant="outlined">
                          <Table size="small">
                            <TableHead>
                              <TableRow>
                                <TableCell>Usuario</TableCell>
                                <TableCell>Rol</TableCell>
                                <TableCell>Acciones</TableCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {memberList.map((m: any) => (
                                <TableRow key={m.id}>
                                  <TableCell>
                                    <Typography variant="body2" fontWeight={600}>
                                      {m.user_display || m.user_email || `Usuario #${m.user}`}
                                    </Typography>
                                  </TableCell>
                                  <TableCell>
                                    <Chip size="small" label={m.role || "member"} variant="outlined" />
                                  </TableCell>
                                  <TableCell>
                                    <Tooltip title="Eliminar miembro">
                                      <IconButton
                                        size="small"
                                        color="error"
                                        onClick={() => removeMemberMut.mutate({ teamId: t.id, memberId: m.id })}
                                      >
                                        <Trash2 size={14} />
                                      </IconButton>
                                    </Tooltip>
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </TableContainer>
                      )}
                    </Box>
                  </Collapse>
                </Paper>
              ))}
            </Stack>
          )}
        </Box>
      )}

      {/* ===================== TAB 2: Menciones ===================== */}
      {tab === 1 && (
        <Box>
          {mentionsLoading ? (
            <Box display="flex" justifyContent="center" py={5}>
              <CircularProgress />
            </Box>
          ) : mentionList.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
              <AtSign size={48} color="#ccc" />
              <Typography color="text.secondary" mt={1}>
                No tienes menciones recientes.
              </Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Tarea</TableCell>
                    <TableCell>Autor</TableCell>
                    <TableCell>Contenido</TableCell>
                    <TableCell>Estado</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {mentionList.map((m: any) => (
                    <TableRow key={m.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {m.task_title || `Tarea #${m.task}`}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {m.author_display || m.author_email || `Usuario #${m.author}`}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {m.content}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={m.is_read ? "Leída" : "Sin leer"}
                          sx={{
                            height: 18, fontSize: 10,
                            bgcolor: m.is_read ? "success.main" : "warning.main",
                            color: "#fff",
                          }}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      )}

      {/* ===================== Dialog: Crear equipo ===================== */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Crear equipo</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Nombre"
              value={createForm.name}
              onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
              fullWidth
              size="small"
            />
            <TextField
              label="Descripción"
              value={createForm.description}
              onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
              fullWidth
              size="small"
              multiline
              minRows={2}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancelar</Button>
          <Button variant="contained" onClick={handleCreate} disabled={!createForm.name || createMut.isPending}>
            Crear
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===================== Dialog: Añadir miembro ===================== */}
      <Dialog open={addMemberTeamId !== null} onClose={() => setAddMemberTeamId(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Añadir miembro</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="ID de usuario"
              value={memberForm.userId}
              onChange={(e) => setMemberForm({ ...memberForm, userId: e.target.value })}
              fullWidth
              size="small"
              helperText="Introduce el ID numérico del usuario"
            />
            <FormControl fullWidth size="small">
              <InputLabel>Rol</InputLabel>
              <Select
                value={memberForm.role}
                label="Rol"
                onChange={(e) => setMemberForm({ ...memberForm, role: e.target.value })}
              >
                <MenuItem value="member">Miembro</MenuItem>
                <MenuItem value="admin">Administrador</MenuItem>
              </Select>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddMemberTeamId(null)}>Cancelar</Button>
          <Button variant="contained" onClick={handleAddMember} disabled={!memberForm.userId || addMemberMut.isPending}>
            Añadir
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
