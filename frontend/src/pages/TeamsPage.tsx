import { formatDate } from "../lib/dates";
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
  useTheme,
} from "@mui/material";
import { Users, Plus, Trash2, UserPlus, AtSign, Mail, Pencil } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  collaborationApi,
  projectsApi,
  invitationsApi,
  type ApiPayload,
} from "../api/resources";
import type {
  Team,
  TeamMember,
  MentionItem,
  ProjectMember,
  Invitation,
  Project,
} from "../types";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import PageHeader from "../components/ui/PageHeader";
import { ErrorState } from "../components/ui/states";
import { TaskListSkeleton } from "../components/ui/skeletons";
import { useTranslation, Trans } from "react-i18next";

export default function TeamsPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [tab, setTab] = useState(0);

  // --- Teams tab state ---
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ name: "", description: "" });
  const [expandedTeam, setExpandedTeam] = useState<number | null>(null);
  const [addMemberTeamId, setAddMemberTeamId] = useState<number | null>(null);
  const [memberForm, setMemberForm] = useState({ userId: "", role: "member" });
  const [editTeam, setEditTeam] = useState<Team | null>(null);
  const [deleteTeamId, setDeleteTeamId] = useState<number | null>(null);

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
      notify.success(t("p.shell.teams.teamCreated"));
      qc.invalidateQueries({ queryKey: ["teams"] });
      setCreateOpen(false);
      setCreateForm({ name: "", description: "" });
    },
  });

  const updateTeamMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiPayload }) =>
      collaborationApi.teams.update(id, data),
    onSuccess: () => {
      notify.success(t("p.shell.teams.teamUpdated"));
      qc.invalidateQueries({ queryKey: ["teams"] });
      setEditTeam(null);
    },
    onError: () => notify.error(t("p.shell.teams.teamUpdateError")),
  });

  const deleteTeamMut = useMutation({
    mutationFn: (id: number) => collaborationApi.teams.remove(id),
    onSuccess: () => {
      notify.success(t("p.shell.teams.teamDeleted"));
      qc.invalidateQueries({ queryKey: ["teams"] });
      setDeleteTeamId(null);
    },
    onError: () => notify.error(t("p.shell.teams.teamDeleteError")),
  });

  const addMemberMut = useMutation({
    mutationFn: ({
      teamId,
      userId,
      role,
    }: {
      teamId: number;
      userId: number;
      role: string;
    }) => collaborationApi.teams.addMember(teamId, userId, role),
    onSuccess: () => {
      notify.success(t("p.shell.teams.memberAdded"));
      setAddMemberTeamId(null);
      if (expandedTeam !== null)
        qc.invalidateQueries({ queryKey: ["team-members", expandedTeam] });
    },
  });

  const removeMemberMut = useMutation({
    mutationFn: ({ teamId, memberId }: { teamId: number; memberId: number }) =>
      collaborationApi.teams.removeMember(teamId, memberId),
    onSuccess: () => {
      notify.info(t("p.shell.teams.memberRemoved"));
      if (expandedTeam !== null)
        qc.invalidateQueries({ queryKey: ["team-members", expandedTeam] });
    },
  });

  // --- Project members queries ---
  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });

  // Preselecciona el primer proyecto cuando la lista carga — evita la
  // pestaña de miembros vacía. Ajuste de estado en render (patrón
  // recomendado): solo corre cuando cambia el primer proyecto, así
  // que el usuario sí puede volver a "" después.
  const firstProjectId = Array.isArray(projects)
    ? ((projects[0] as { id?: number } | undefined)?.id ?? null)
    : null;
  const [autoSelectedFor, setAutoSelectedFor] = useState<number | null>(firstProjectId);
  if (firstProjectId !== autoSelectedFor) {
    setAutoSelectedFor(firstProjectId);
    if (selectedProjectId === "" && firstProjectId != null) setSelectedProjectId(firstProjectId);
  }

  const projectMembersQuery = useQuery({
    queryKey: ["project-members", selectedProjectId],
    queryFn: () => collaborationApi.projectMembers.list(selectedProjectId as number),
    enabled: !!selectedProjectId,
  });

  const inviteMemberMut = useMutation({
    mutationFn: ({
      projectId,
      email,
      role,
    }: {
      projectId: number;
      email: string;
      role: string;
    }) => collaborationApi.projectMembers.invite(projectId, { email, role }),
    onSuccess: () => {
      notify.success(t("p.shell.teams.inviteSent"));
      qc.invalidateQueries({ queryKey: ["project-members", selectedProjectId] });
      qc.invalidateQueries({ queryKey: ["invitations"] });
      setInviteOpen(false);
    },
  });

  const updateMemberRoleMut = useMutation({
    mutationFn: ({ id, role }: { id: number; role: string }) =>
      collaborationApi.projectMembers.update(id, { role }),
    onSuccess: () => {
      notify.success(t("p.shell.teams.roleUpdated"));
      qc.invalidateQueries({ queryKey: ["project-members", selectedProjectId] });
    },
    onError: () => notify.error(t("p.shell.teams.roleUpdateError")),
  });

  const removeProjectMemberMut = useMutation({
    mutationFn: (id: number) => collaborationApi.projectMembers.remove(id),
    onSuccess: () => {
      notify.success(t("p.shell.teams.memberRemovedProject"));
      qc.invalidateQueries({ queryKey: ["project-members", selectedProjectId] });
    },
    onError: () => notify.error(t("p.shell.teams.memberRemoveError")),
  });

  // --- Invitations ---
  const { data: invitationsData, isLoading: invitationsLoading } = useQuery({
    queryKey: ["invitations"],
    queryFn: invitationsApi.list,
  });
  const invitationList: Invitation[] =
    (invitationsData as { results?: Invitation[] })?.results ??
    (invitationsData as Invitation[]) ??
    [];

  const acceptInvMut = useMutation({
    mutationFn: (id: number) => invitationsApi.accept(id),
    onSuccess: () => {
      notify.success(t("p.shell.teams.inviteAccepted"));
      qc.invalidateQueries({ queryKey: ["invitations"] });
    },
  });
  const declineInvMut = useMutation({
    mutationFn: (id: number) => invitationsApi.decline(id),
    onSuccess: () => {
      notify.info(t("p.shell.teams.inviteDeclined"));
      qc.invalidateQueries({ queryKey: ["invitations"] });
    },
  });

  const teamList: Team[] =
    (teams as { results?: Team[] })?.results ?? (teams as Team[]) ?? [];
  const mentionList: MentionItem[] =
    (mentions as { results?: MentionItem[] })?.results ??
    (mentions as MentionItem[]) ??
    [];
  const memberList: TeamMember[] =
    (membersQuery.data as { results?: TeamMember[] })?.results ??
    (membersQuery.data as TeamMember[]) ??
    [];
  const projectList = (projects as Project[]) ?? [];
  const projectMemberList: ProjectMember[] =
    (projectMembersQuery.data as { results?: ProjectMember[] })?.results ??
    (projectMembersQuery.data as ProjectMember[]) ??
    [];

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
      <PageHeader
        title={
          <>
            <Users size={22} style={{ color: theme.palette.primary.main, verticalAlign: "text-bottom", marginRight: 8 }} />
            {t("p.shell.teams.title")}
          </>
        }
        description={<Trans i18nKey="p.shell.teams.description" />}
      />

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab icon={<Users size={16} />} iconPosition="start" label={t("nav.teams")} />
        <Tab
          icon={<AtSign size={16} />}
          iconPosition="start"
          label={t("p.shell.teams.tabMentions")}
        />
        <Tab
          icon={<UserPlus size={16} />}
          iconPosition="start"
          label={t("p.shell.teams.tabProjectMembers")}
        />
        <Tab
          icon={<Mail size={16} />}
          iconPosition="start"
          label={t("p.shell.teams.tabInvitations")}
        />
      </Tabs>

      {/* ===================== TAB 1: Equipos ===================== */}
      {tab === 0 && (
        <Box>
          <Stack direction="row" justifyContent="flex-end" mb={2}>
            <Button
              variant="contained"
              startIcon={<Plus size={18} />}
              onClick={() => {
                setCreateForm({ name: "", description: "" });
                setCreateOpen(true);
              }}
            >
              {t("p.shell.teams.newTeam")}
            </Button>
          </Stack>

          {teamsLoading ? (
            <TaskListSkeleton rows={4} />
          ) : teamList.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
              <Users size={48} color="text.disabled" />
              <Typography color="text.secondary" mt={1}>
                {t("p.shell.teams.noTeams")}
              </Typography>
            </Paper>
          ) : (
            <Stack spacing={2}>
              {teamList.map((team) => (
                <Paper key={team.id} variant="outlined">
                  <Stack
                    direction="row"
                    alignItems="center"
                    justifyContent="space-between"
                    sx={{ p: 2, cursor: "pointer" }}
                    onClick={() =>
                      setExpandedTeam(expandedTeam === team.id ? null : team.id)
                    }
                  >
                    <Stack direction="row" alignItems="center" spacing={1.5}>
                      <Users size={20} style={{ color: theme.palette.primary.main }} />
                      <Box>
                        <Typography variant="subtitle1" fontWeight={600}>
                          {team.name}
                        </Typography>
                        {team.description && (
                          <Typography variant="caption" color="text.secondary">
                            {team.description}
                          </Typography>
                        )}
                      </Box>
                    </Stack>
                    <Stack direction="row" alignItems="center" spacing={1}>
                      {typeof team.member_count === "number" && (
                        <Chip
                          size="small"
                          label={t("p.shell.teams.memberCount", {
                            count: team.member_count,
                          })}
                          variant="outlined"
                        />
                      )}
                      <Button
                        size="small"
                        startIcon={<UserPlus size={14} />}
                        onClick={(e) => {
                          e.stopPropagation();
                          setAddMemberTeamId(team.id);
                          setMemberForm({ userId: "", role: "member" });
                        }}
                      >
                        {t("p.shell.teams.add")}
                      </Button>
                      <Tooltip title={t("p.shell.teams.editTeam")}>
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditTeam(team);
                          }}
                        >
                          <Pencil size={14} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title={t("p.shell.teams.deleteTeam")}>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteTeamId(team.id);
                          }}
                        >
                          <Trash2 size={14} />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </Stack>

                  <Collapse in={expandedTeam === team.id}>
                    <Box sx={{ p: 2, pt: 0 }}>
                      {membersQuery.isLoading ? (
                        <TaskListSkeleton rows={2} />
                      ) : memberList.length === 0 ? (
                        <Typography color="text.secondary" variant="body2" sx={{ py: 1 }}>
                          {t("p.shell.teams.noMembers")}
                        </Typography>
                      ) : (
                        <TableContainer component={Paper} variant="outlined">
                          <Table size="small">
                            <TableHead>
                              <TableRow>
                                <TableCell>{t("p.shell.teams.colUser")}</TableCell>
                                <TableCell>{t("p.shell.teams.colRole")}</TableCell>
                                <TableCell>{t("p.shell.teams.colActions")}</TableCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {memberList.map((m) => (
                                <TableRow key={m.id}>
                                  <TableCell>
                                    <Typography variant="body2" fontWeight={600}>
                                      {m.user_display ||
                                        m.user_email ||
                                        t("p.shell.teams.userNumber", {
                                          id: m.user,
                                        })}
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
                                    <Tooltip title={t("p.shell.teams.removeMember")}>
                                      <IconButton
                                        size="small"
                                        color="error"
                                        onClick={async () => {
                                          if (
                                            await confirm(
                                              t("p.shell.teams.confirmRemoveMember", {
                                                name:
                                                  m.user_display ||
                                                  m.user_email ||
                                                  t("p.shell.teams.thisMember"),
                                              }),
                                              { confirmLabel: t("p.shell.teams.removeMember") },
                                            )
                                          )
                                            removeMemberMut.mutate({
                                              teamId: team.id,
                                              memberId: m.id,
                                            });
                                        }}
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
            <TaskListSkeleton rows={3} />
          ) : mentionList.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
              <AtSign size={48} color="text.disabled" />
              <Typography color="text.secondary" mt={1}>
                {t("p.shell.teams.noMentions")}
              </Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t("p.shell.teams.colTask")}</TableCell>
                    <TableCell>{t("p.shell.teams.colAuthor")}</TableCell>
                    <TableCell>{t("p.shell.teams.colContent")}</TableCell>
                    <TableCell>{t("p.shell.teams.colStatus")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {mentionList.map((m) => (
                    <TableRow key={m.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {m.task_title || t("p.shell.teams.taskNumber", { id: m.task })}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {m.author_display ||
                            m.author_email ||
                            t("p.shell.teams.userNumber", { id: m.author })}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{
                            maxWidth: 320,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {m.content}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={
                            m.is_read
                              ? t("p.shell.teams.mentionRead")
                              : t("p.shell.teams.mentionUnread")
                          }
                          sx={{
                            height: 18,
                            fontSize: 10,
                            bgcolor: m.is_read ? "success.main" : "warning.main",
                            color: "common.white",
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
              <InputLabel>{t("p.shell.project")}</InputLabel>
              <Select
                value={selectedProjectId}
                label={t("p.shell.project")}
                onChange={(e) => setSelectedProjectId(e.target.value as number | "")}
              >
                <MenuItem value="">
                  <em>{t("p.shell.teams.selectProject")}</em>
                </MenuItem>
                {projectList.map((p) => (
                  <MenuItem key={p.id} value={p.id}>
                    {p.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Box flexGrow={1} />
            <Button
              variant="contained"
              startIcon={<UserPlus size={18} />}
              disabled={!selectedProjectId}
              onClick={() => {
                setInviteForm({ email: "", role: "member" });
                setInviteOpen(true);
              }}
            >
              {t("p.shell.teams.inviteMember")}
            </Button>
          </Stack>

          {!selectedProjectId ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
              <Users size={48} color="text.disabled" />
              <Typography color="text.secondary" mt={1}>
                {t("p.shell.teams.selectProjectHint")}
              </Typography>
            </Paper>
          ) : projectMembersQuery.isLoading ? (
            <TaskListSkeleton rows={4} />
          ) : projectMembersQuery.isError ? (
            <ErrorState
              title={t("p.shell.teams.loadMembersError")}
              onRetry={() => void projectMembersQuery.refetch()}
            />
          ) : projectMemberList.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
              <Users size={48} color="text.disabled" />
              <Typography color="text.secondary" mt={1}>
                {t("p.shell.teams.noProjectMembers")}
              </Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t("p.shell.teams.colUser")}</TableCell>
                    <TableCell>{t("p.shell.teams.colRole")}</TableCell>
                    <TableCell>{t("p.shell.teams.colJoined")}</TableCell>
                    <TableCell align="right">{t("p.shell.teams.colActions")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {projectMemberList.map((m) => (
                    <TableRow key={m.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {m.user_display ||
                            m.user_email ||
                            m.email ||
                            t("p.shell.teams.userNumber", { id: m.user })}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Select
                          size="small"
                          value={m.role || "viewer"}
                          onChange={(e) =>
                            updateMemberRoleMut.mutate({ id: m.id, role: e.target.value })
                          }
                          variant="outlined"
                          sx={{ minWidth: 110 }}
                        >
                          <MenuItem value="owner">
                            {t("p.shell.teams.roleOwner")}
                          </MenuItem>
                          <MenuItem value="editor">
                            {t("p.shell.teams.roleEditor")}
                          </MenuItem>
                          <MenuItem value="viewer">
                            {t("p.shell.teams.roleViewer")}
                          </MenuItem>
                        </Select>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {m.joined_at || m.created_at
                            ? formatDate(m.joined_at || m.created_at)
                            : "—"}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <IconButton
                          size="small"
                          color="error"
                          aria-label={t("p.shell.teams.removeMember")}
                          onClick={async () => {
                            if (
                              await confirm(
                                t("p.shell.teams.confirmRemoveProjectMember", {
                                  name:
                                    m.user_display ||
                                    m.user_email ||
                                    t("p.shell.teams.thisMember"),
                                }),
                                { confirmLabel: t("p.shell.teams.removeMember") },
                              )
                            ) {
                              removeProjectMemberMut.mutate(m.id);
                            }
                          }}
                        >
                          <Trash2 size={16} />
                        </IconButton>
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
            <TaskListSkeleton rows={3} />
          ) : invitationList.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
              <Mail size={48} color="text.disabled" />
              <Typography color="text.secondary" mt={1}>
                {t("p.shell.teams.noInvitations")}
              </Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t("auth.email")}</TableCell>
                    <TableCell>{t("p.shell.teams.colRole")}</TableCell>
                    <TableCell>{t("p.shell.teams.colStatus")}</TableCell>
                    <TableCell>{t("p.shell.teams.colDate")}</TableCell>
                    <TableCell>{t("p.shell.teams.colActions")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {invitationList.map((inv) => (
                    <TableRow key={inv.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {inv.email}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={inv.role || "member"}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={inv.status}
                          sx={{
                            height: 18,
                            fontSize: 10,
                            bgcolor:
                              inv.status === "pending"
                                ? "warning.main"
                                : inv.status === "accepted"
                                  ? "success.main"
                                  : "error.main",
                            color: "common.white",
                          }}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {inv.created_at ? formatDate(inv.created_at) : "—"}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {inv.status === "pending" && (
                          <Stack direction="row" spacing={1}>
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => acceptInvMut.mutate(inv.id)}
                              disabled={acceptInvMut.isPending}
                            >
                              {t("p.shell.teams.accept")}
                            </Button>
                            <Button
                              size="small"
                              color="error"
                              variant="outlined"
                              onClick={() => declineInvMut.mutate(inv.id)}
                              disabled={declineInvMut.isPending}
                            >
                              {t("p.shell.teams.decline")}
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
      <Dialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.shell.teams.createTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("common.name")}
              value={createForm.name}
              onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
              fullWidth
              size="small"
            />
            <TextField
              label={t("p.shell.teams.fieldDescription")}
              value={createForm.description}
              onChange={(e) =>
                setCreateForm({ ...createForm, description: e.target.value })
              }
              fullWidth
              size="small"
              multiline
              minRows={2}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={!createForm.name || createMut.isPending}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===================== Dialog: Añadir miembro ===================== */}
      <Dialog
        open={addMemberTeamId !== null}
        onClose={() => setAddMemberTeamId(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.shell.teams.addMemberTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("p.shell.teams.userIdLabel")}
              value={memberForm.userId}
              onChange={(e) => setMemberForm({ ...memberForm, userId: e.target.value })}
              fullWidth
              size="small"
              helperText={t("p.shell.teams.userIdHelp")}
            />
            <FormControl fullWidth size="small">
              <InputLabel>{t("p.shell.teams.colRole")}</InputLabel>
              <Select
                value={memberForm.role}
                label={t("p.shell.teams.colRole")}
                onChange={(e) => setMemberForm({ ...memberForm, role: e.target.value })}
              >
                <MenuItem value="member">{t("p.shell.teams.roleMember")}</MenuItem>
                <MenuItem value="admin">{t("p.shell.teams.roleAdmin")}</MenuItem>
              </Select>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddMemberTeamId(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={handleAddMember}
            disabled={!memberForm.userId || addMemberMut.isPending}
          >
            {t("p.shell.teams.add")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===================== Dialog: Invitar miembro a proyecto ===================== */}
      <Dialog
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.shell.teams.inviteMember")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("p.shell.teams.inviteEmailLabel")}
              value={inviteForm.email}
              onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
              fullWidth
              size="small"
              helperText={t("p.shell.teams.inviteEmailHelp")}
            />
            <FormControl fullWidth size="small">
              <InputLabel>{t("p.shell.teams.colRole")}</InputLabel>
              <Select
                value={inviteForm.role}
                label={t("p.shell.teams.colRole")}
                onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value })}
              >
                <MenuItem value="admin">{t("p.shell.teams.roleAdmin")}</MenuItem>
                <MenuItem value="member">{t("p.shell.teams.roleMember")}</MenuItem>
                <MenuItem value="viewer">{t("p.shell.teams.roleReader")}</MenuItem>
              </Select>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setInviteOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={handleInviteMember}
            disabled={!inviteForm.email || inviteMemberMut.isPending}
          >
            {t("p.shell.teams.invite")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit team dialog */}
      <Dialog open={!!editTeam} onClose={() => setEditTeam(null)} fullWidth maxWidth="sm">
        <DialogTitle>{t("p.shell.teams.editTeam")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("common.name")}
              fullWidth
              defaultValue={editTeam?.name || ""}
              onChange={(e) =>
                setEditTeam((prev) => (prev ? { ...prev, name: e.target.value } : prev))
              }
            />
            <TextField
              label={t("p.shell.teams.fieldDescription")}
              fullWidth
              multiline
              rows={2}
              defaultValue={editTeam?.description || ""}
              onChange={(e) =>
                setEditTeam((prev) =>
                  prev ? { ...prev, description: e.target.value } : prev,
                )
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditTeam(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={updateTeamMut.isPending}
            onClick={() =>
              editTeam &&
              updateTeamMut.mutate({
                id: editTeam.id,
                data: { name: editTeam.name, description: editTeam.description },
              })
            }
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete team confirmation */}
      <Dialog
        open={deleteTeamId !== null}
        onClose={() => setDeleteTeamId(null)}
        maxWidth="xs"
      >
        <DialogTitle>{t("p.shell.teams.deleteTeam")}</DialogTitle>
        <DialogContent>
          <Alert severity="warning">{t("p.shell.teams.deleteWarning")}</Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTeamId(null)}>{t("common.cancel")}</Button>
          <Button
            color="error"
            variant="contained"
            disabled={deleteTeamMut.isPending}
            onClick={() => deleteTeamMut.mutate(deleteTeamId!)}
          >
            {t("common.delete")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
