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
import { Users, Plus, Trash2, UserPlus, AtSign, Mail } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { collaborationApi, projectsApi, invitationsApi } from "../api/resources";
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

  // --- Project members tab state ---
  const [selectedProjectId, setSelectedProjectId] = useState<number | "">("");
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteForm, setInviteForm] = useState({ email: "", role: "member" });

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

  // --- Project members queries ---
  const { data: projects, isLoading: projectsLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });

  const projectMembersQuery = useQuery({
    queryKey: ["project-members", selectedProjectId],
    queryFn: () => collaborationApi.projectMembers.list(selectedProjectId as number),
    enabled: !!selectedProjectId,
  });

  const inviteMemberMut = useMutation({
    mutationFn: ({ projectId, email, role }: { projectId: number; email: string; role: string }) =>
      collaborationApi.projectMembers.invite(projectId, { email, role }),
    onSuccess: () => {
      notify.success("Invitación enviada");
      qc.invalidateQueries({ queryKey: ["project-members", selectedProjectId] });
      qc.invalidateQueries({ queryKey: ["invitations"] });
      setInviteOpen(false);
    },
  });

  // --- Invitations ---
  const { data: invitationsData, isLoading: invitationsLoading } = useQuery({
    queryKey: ["invitations"],
    queryFn: invitationsApi.list,
  });
  const invitationList = (invitationsData as any)?.results ?? (invitationsData as any) ?? [];

  const acceptInvMut = useMutation({
    mutationFn: (id: number) => invitationsApi.accept(id),
    onSuccess: () => {
      notify.success("Invitación aceptada");
      qc.invalidateQueries({ queryKey: ["invitations"] });
    },
  });
  const declineInvMut = useMutation({
    mutationFn: (id: number) => invitationsApi.decline(id),
    onSuccess: () => {
      notify.info("Invitación rechazada");
      qc.invalidateQueries({ queryKey: ["invitations"] });
    },
  });

  const teamList = (teams as any)?.results ?? (teams as any) ?? [];
  const mentionList = (mentions as any)?.results ?? (mentions as any) ?? [];
  const memberList = (membersQuery.data as any)?.results ?? (membersQuery.data as any) ?? [];
  const projectList = (projects as any) ?? [];
  const projectMemberList = (projectMembersQuery.data as any)?.results ?? (projectMembersQuery.data as any) ?? [];

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

  const handleInviteMember = () => {
    if (!selectedProjectId || !inviteForm.email) return;
    inviteMemberMut.mutate({
      projectId: Number(selectedProjectId),
      email: inviteForm.email,
      role: inviteForm.role,
    });
  };

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" spacing={1} mb={1}>
        <Users size={24} color="#1976d2" />
        <Typography variant="h5" fontWeight={700}>Equipos y Colaboración</Typography>
      </Stack>
      <Typography variant="body2" color="text.secondary" mb={2}>
        Gestiona equipos de trabajo, invita miembros a proyectos y consulta menciones.
        Los <strong>equipos</strong> agrupan personas por área (frontend, backend, devops).
        Los <strong>miembros de proyecto</strong> controlan quién tiene acceso a cada proyecto y con qué rol.
        Las <strong>menciones</strong> te avisan cuando alguien te etiqueta en una tarea o comentario.
      </Typography>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab icon={<Users size={16} />} iconPosition="start" label="Equipos" />
        <Tab icon={<AtSign size={16} />} iconPosition="start" label="Menciones" />
        <Tab icon={<UserPlus size={16} />} iconPosition="start" label="Miembros de Proyecto" />
        <Tab icon={<Mail size={16} />} iconPosition="start" label="Invitaciones" />
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
              <Users size={48} color="text.disabled" />
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
              <AtSign size={48} color="text.disabled" />
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

      {/* ===================== TAB 3: Miembros de Proyecto ===================== */}
      {tab === 2 && (
        <Box>
          <Stack direction="row" alignItems="center" spacing={2} mb={2}>
            <FormControl size="small" sx={{ minWidth: 260 }}>
              <InputLabel>Proyecto</InputLabel>
              <Select
                value={selectedProjectId}
                label="Proyecto"
                onChange={(e) => setSelectedProjectId(e.target.value as number | "")}
              >
                <MenuItem value="">
                  <em>Selecciona un proyecto</em>
                </MenuItem>
                {projectList.map((p: any) => (
                  <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <Box flexGrow={1} />
            <Button
              variant="contained"
              startIcon={<UserPlus size={18} />}
              disabled={!selectedProjectId}
              onClick={() => { setInviteForm({ email: "", role: "member" }); setInviteOpen(true); }}
            >
              Invitar miembro
            </Button>
          </Stack>

          {!selectedProjectId ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
              <Users size={48} color="text.disabled" />
              <Typography color="text.secondary" mt={1}>
                Selecciona un proyecto para ver sus miembros.
              </Typography>
            </Paper>
          ) : projectMembersQuery.isLoading ? (
            <Box display="flex" justifyContent="center" py={5}>
              <CircularProgress />
            </Box>
          ) : projectMembersQuery.isError ? (
            <Alert severity="error">Error al cargar los miembros del proyecto.</Alert>
          ) : projectMemberList.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
              <Users size={48} color="text.disabled" />
              <Typography color="text.secondary" mt={1}>
                Este proyecto no tiene miembros todavía.
              </Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Usuario</TableCell>
                    <TableCell>Rol</TableCell>
                    <TableCell>Fecha de ingreso</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {projectMemberList.map((m: any) => (
                    <TableRow key={m.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {m.user_display || m.user_email || m.email || `Usuario #${m.user}`}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={m.role || "member"}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {m.joined_at || m.created_at ? new Date(m.joined_at || m.created_at).toLocaleDateString() : "—"}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      )}

      {/* ===================== TAB 4: Invitaciones ===================== */}
      {tab === 3 && (
        <Box>
          {invitationsLoading ? (
            <Box display="flex" justifyContent="center" py={5}>
              <CircularProgress />
            </Box>
          ) : invitationList.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
              <Mail size={48} color="text.disabled" />
              <Typography color="text.secondary" mt={1}>
                No tienes invitaciones.
              </Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Email</TableCell>
                    <TableCell>Rol</TableCell>
                    <TableCell>Estado</TableCell>
                    <TableCell>Fecha</TableCell>
                    <TableCell>Acciones</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {invitationList.map((inv: any) => (
                    <TableRow key={inv.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>{inv.email}</Typography>
                      </TableCell>
                      <TableCell>
                        <Chip size="small" label={inv.role || "member"} variant="outlined" />
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={inv.status}
                          sx={{
                            height: 18, fontSize: 10,
                            bgcolor: inv.status === "pending" ? "warning.main" : inv.status === "accepted" ? "success.main" : "error.main",
                            color: "#fff",
                          }}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {inv.created_at ? new Date(inv.created_at).toLocaleDateString() : "—"}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {inv.status === "pending" && (
                          <Stack direction="row" spacing={1}>
                            <Button size="small" variant="outlined" onClick={() => acceptInvMut.mutate(inv.id)} disabled={acceptInvMut.isPending}>
                              Aceptar
                            </Button>
                            <Button size="small" color="error" variant="outlined" onClick={() => declineInvMut.mutate(inv.id)} disabled={declineInvMut.isPending}>
                              Rechazar
                            </Button>
                          </Stack>
                        )}
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

      {/* ===================== Dialog: Invitar miembro a proyecto ===================== */}
      <Dialog open={inviteOpen} onClose={() => setInviteOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Invitar miembro</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Email o nombre de usuario"
              value={inviteForm.email}
              onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
              fullWidth
              size="small"
              helperText="Introduce el email o username del usuario a invitar"
            />
            <FormControl fullWidth size="small">
              <InputLabel>Rol</InputLabel>
              <Select
                value={inviteForm.role}
                label="Rol"
                onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value })}
              >
                <MenuItem value="admin">Administrador</MenuItem>
                <MenuItem value="member">Miembro</MenuItem>
                <MenuItem value="viewer">Lector</MenuItem>
              </Select>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setInviteOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={handleInviteMember}
            disabled={!inviteForm.email || inviteMemberMut.isPending}
          >
            Invitar
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

