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
  IconButton,
  Tooltip,
  Tabs,
  Tab,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Link as MuiLink,
} from "@mui/material";
import {
  Github,
  RefreshCw,
  Trash2,
  Link2,
  Download,
  Settings,
  ExternalLink,
  Plus,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  githubApi,
  type GitHubInstallation,
  type GitHubRepo,
  type GitHubIssue,
  type GitHubIssueLink,
} from "../api/resources";
import { notify } from "../notify";

/* ---------- helpers ---------- */

function TabPanel({
  children,
  value,
  index,
}: {
  children: React.ReactNode;
  value: number;
  index: number;
}) {
  if (value !== index) return null;
  return <Box sx={{ py: 3 }}>{children}</Box>;
}

function LoadingBox() {
  return (
    <Box display="flex" justifyContent="center" py={5}>
      <CircularProgress />
    </Box>
  );
}

function EmptyState({ icon, message }: { icon: React.ReactNode; message: string }) {
  return (
    <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
      <Box display="flex" justifyContent="center" mb={1}>
        {icon}
      </Box>
      <Typography color="text.secondary">{message}</Typography>
    </Paper>
  );
}

/* ---------- main component ---------- */

export default function GitHubPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState(0);

  /* ----- Instalaciones ----- */
  const { data: installations, isLoading: loadingInst } = useQuery({
    queryKey: ["github-installations"],
    queryFn: githubApi.listInstallations,
  });

  const discoverMut = useMutation({
    mutationFn: githubApi.discoverRepos,
    onSuccess: (data) => {
      notify.success(
        data.message || `Se descubrieron ${data.new} repos nuevos (${data.total} total)`
      );
      qc.invalidateQueries({ queryKey: ["github-repos"] });
      qc.invalidateQueries({ queryKey: ["github-installations"] });
    },
    onError: () => notify.error("Error al descubrir repos"),
  });

  const removeInstMut = useMutation({
    mutationFn: githubApi.removeInstallation,
    onSuccess: () => {
      notify.info("Instalación eliminada");
      qc.invalidateQueries({ queryKey: ["github-installations"] });
      qc.invalidateQueries({ queryKey: ["github-repos"] });
    },
    onError: () => notify.error("Error al eliminar instalación"),
  });

  /* ----- Repos ----- */
  const { data: repos, isLoading: loadingRepos } = useQuery({
    queryKey: ["github-repos"],
    queryFn: githubApi.listRepos,
  });

  const syncRepoMut = useMutation({
    mutationFn: githubApi.syncRepo,
    onSuccess: (data) => {
      notify.success(data.message || "Repo sincronizado");
      qc.invalidateQueries({ queryKey: ["github-repos"] });
    },
    onError: () => notify.error("Error al sincronizar repo"),
  });

  const updateRepoMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<GitHubRepo> }) =>
      githubApi.updateRepo(id, data),
    onSuccess: () => {
      notify.success("Repo actualizado");
      qc.invalidateQueries({ queryKey: ["github-repos"] });
    },
    onError: () => notify.error("Error al actualizar repo"),
  });

  /* ----- Issues & Links ----- */
  const [selectedRepoId, setSelectedRepoId] = useState<number | "">("");
  const [issueState, setIssueState] = useState<string>("open");
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importLabel, setImportLabel] = useState("");
  const [linkDialogOpen, setLinkDialogOpen] = useState(false);
  const [linkForm, setLinkForm] = useState({
    taskId: "",
    repoId: "" as number | "",
    issueNumber: "",
  });

  const { data: issues, isLoading: loadingIssues } = useQuery({
    queryKey: ["github-issues", selectedRepoId, issueState],
    queryFn: () => githubApi.listRepoIssues(selectedRepoId as number, issueState),
    enabled: selectedRepoId !== "",
  });

  const { data: links, isLoading: loadingLinks } = useQuery({
    queryKey: ["github-links"],
    queryFn: githubApi.listLinks,
  });

  const importMut = useMutation({
    mutationFn: () =>
      githubApi.importIssues(selectedRepoId as number, issueState, importLabel),
    onSuccess: (data) => {
      notify.success(
        `Importadas ${data.imported} issues (${data.skipped} omitidas de ${data.total} total)`
      );
      setImportDialogOpen(false);
      setImportLabel("");
      qc.invalidateQueries({ queryKey: ["github-links"] });
    },
    onError: () => notify.error("Error al importar issues"),
  });

  const createLinkMut = useMutation({
    mutationFn: () =>
      githubApi.createLinkForTask(Number(linkForm.taskId), Number(linkForm.repoId)),
    onSuccess: () => {
      notify.success("Link creado correctamente");
      setLinkDialogOpen(false);
      setLinkForm({ taskId: "", repoId: "", issueNumber: "" });
      qc.invalidateQueries({ queryKey: ["github-links"] });
    },
    onError: () => notify.error("Error al crear link"),
  });

  const syncLinkMut = useMutation({
    mutationFn: githubApi.syncLink,
    onSuccess: (data) => {
      notify.success(data.message || "Link sincronizado");
      qc.invalidateQueries({ queryKey: ["github-links"] });
    },
    onError: () => notify.error("Error al sincronizar link"),
  });

  const instList: GitHubInstallation[] = installations || [];
  const repoList: GitHubRepo[] = repos || [];
  const issueList: GitHubIssue[] = issues || [];
  const linkList: GitHubIssueLink[] = links || [];

  /* ---------- render ---------- */

  return (
    <Box maxWidth={1000} mx="auto">
      <Stack direction="row" alignItems="center" spacing={1} mb={3}>
        <Github size={28} color="#1976d2" />
        <Typography variant="h5" fontWeight={700}>
          Integración GitHub
        </Typography>
      </Stack>

      <Alert severity="info" sx={{ mb: 2 }}>
        Conecta tu cuenta de GitHub para sincronizar repos, importar issues y enlazarlos
        con tus tareas. Usa las pestañas para gestionar instalaciones, repos y links.
      </Alert>

      <Paper variant="outlined">
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          sx={{ borderBottom: 1, borderColor: "divider", px: 2 }}
        >
          <Tab
            icon={<Settings size={16} />}
            iconPosition="start"
            label="Instalaciones"
          />
          <Tab label="Repos" />
          <Tab
            icon={<Link2 size={16} />}
            iconPosition="start"
            label="Issues & Links"
          />
        </Tabs>

        {/* ===== Tab 1: Instalaciones ===== */}
        <TabPanel value={tab} index={0}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="subtitle1" fontWeight={600}>
              Instalaciones de GitHub App
            </Typography>
            <Button
              variant="contained"
              size="small"
              startIcon={<RefreshCw size={16} />}
              onClick={() => discoverMut.mutate()}
              disabled={discoverMut.isPending}
            >
              {discoverMut.isPending ? "Descubriendo..." : "Descubrir repos"}
            </Button>
          </Stack>

          {loadingInst ? (
            <LoadingBox />
          ) : instList.length === 0 ? (
            <EmptyState
              icon={<Github size={48} color="#ccc" />}
              message="No hay instalaciones. Instala la GitHub App en tu cuenta u organización para empezar."
            />
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Cuenta</TableCell>
                    <TableCell>Tipo</TableCell>
                    <TableCell>Usuario</TableCell>
                    <TableCell>Instalación ID</TableCell>
                    <TableCell>Creada</TableCell>
                    <TableCell>Acciones</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {instList.map((inst) => (
                    <TableRow key={inst.id}>
                      <TableCell>
                        <Stack direction="row" alignItems="center" spacing={1}>
                          {inst.avatar_url && (
                            <img
                              src={inst.avatar_url}
                              alt={inst.account_login}
                              style={{ width: 24, height: 24, borderRadius: 4 }}
                            />
                          )}
                          <Typography variant="body2" fontWeight={600}>
                            {inst.account_login}
                          </Typography>
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={inst.account_type}
                          sx={{ height: 20, fontSize: 11 }}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{inst.github_username}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {inst.installation_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {new Date(inst.created_at).toLocaleDateString("es-ES")}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Tooltip title="Eliminar instalación">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => removeInstMut.mutate(inst.id)}
                            disabled={removeInstMut.isPending}
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
        </TabPanel>

        {/* ===== Tab 2: Repos ===== */}
        <TabPanel value={tab} index={1}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="subtitle1" fontWeight={600}>
              Repositorios sincronizados
            </Typography>
            <Button
              variant="outlined"
              size="small"
              startIcon={<RefreshCw size={16} />}
              onClick={() => qc.invalidateQueries({ queryKey: ["github-repos"] })}
            >
              Refrescar
            </Button>
          </Stack>

          {loadingRepos ? (
            <LoadingBox />
          ) : repoList.length === 0 ? (
            <EmptyState
              icon={<Github size={48} color="#ccc" />}
              message="No hay repos descubiertos. Ve a la pestaña Instalaciones y pulsa «Descubrir repos»."
            />
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Repositorio</TableCell>
                    <TableCell>Owner</TableCell>
                    <TableCell>Branch</TableCell>
                    <TableCell>Visibilidad</TableCell>
                    <TableCell>Sincronización</TableCell>
                    <TableCell>Acciones</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {repoList.map((repo) => (
                    <TableRow key={repo.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {repo.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {repo.full_name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{repo.owner}</Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={repo.default_branch}
                          sx={{ height: 20, fontSize: 11 }}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={repo.is_private ? "Privado" : "Público"}
                          sx={{
                            height: 20,
                            fontSize: 11,
                            bgcolor: repo.is_private ? "warning.light" : "success.light",
                            color: "#fff",
                          }}
                        />
                      </TableCell>
                      <TableCell>
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <Switch
                            size="small"
                            checked={repo.sync_enabled}
                            onChange={(e) =>
                              updateRepoMut.mutate({
                                id: repo.id,
                                data: { sync_enabled: e.target.checked },
                              })
                            }
                          />
                          <Typography variant="caption" color="text.secondary">
                            {repo.sync_enabled ? "Activada" : "Desactivada"}
                          </Typography>
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Tooltip title="Sincronizar repo">
                          <IconButton
                            size="small"
                            onClick={() => syncRepoMut.mutate(repo.id)}
                            disabled={syncRepoMut.isPending}
                          >
                            <RefreshCw size={14} />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </TabPanel>

        {/* ===== Tab 3: Issues & Links ===== */}
        <TabPanel value={tab} index={2}>
          {/* Selector de repo + issues */}
          <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
            <Stack direction="row" spacing={2} alignItems="center" mb={2}>
              <FormControl size="small" sx={{ minWidth: 300 }}>
                <InputLabel>Seleccionar repo</InputLabel>
                <Select
                  value={selectedRepoId}
                  label="Seleccionar repo"
                  onChange={(e) => setSelectedRepoId(e.target.value as number)}
                >
                  <MenuItem value="">
                    <em>— Ninguno —</em>
                  </MenuItem>
                  {repoList.map((r) => (
                    <MenuItem key={r.id} value={r.id}>
                      {r.full_name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel>Estado</InputLabel>
                <Select
                  value={issueState}
                  label="Estado"
                  onChange={(e) => setIssueState(e.target.value as string)}
                >
                  <MenuItem value="open">Abiertos</MenuItem>
                  <MenuItem value="closed">Cerrados</MenuItem>
                  <MenuItem value="all">Todos</MenuItem>
                </Select>
              </FormControl>
              <Button
                variant="contained"
                size="small"
                startIcon={<Download size={16} />}
                onClick={() => setImportDialogOpen(true)}
                disabled={selectedRepoId === ""}
              >
                Importar issues
              </Button>
            </Stack>

            {selectedRepoId === "" ? (
              <Alert severity="info">
                Selecciona un repositorio para ver sus issues.
              </Alert>
            ) : loadingIssues ? (
              <LoadingBox />
            ) : issueList.length === 0 ? (
              <EmptyState
                icon={<Github size={40} color="#ccc" />}
                message="Este repo no tiene issues con el estado seleccionado."
              />
            ) : (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell width={60}>#</TableCell>
                      <TableCell>Título</TableCell>
                      <TableCell>Estado</TableCell>
                      <TableCell>Labels</TableCell>
                      <TableCell>Link</TableCell>
                      <TableCell>URL</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {issueList.map((issue) => (
                      <TableRow key={issue.id}>
                        <TableCell>
                          <Typography variant="body2" fontFamily="monospace">
                            #{issue.number}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{issue.title}</Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            label={issue.state}
                            sx={{
                              height: 20,
                              fontSize: 11,
                              bgcolor:
                                issue.state === "open" ? "success.light" : "grey.400",
                              color: "#fff",
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <Stack direction="row" spacing={0.5} flexWrap="wrap">
                            {(issue.labels || []).map((l) => (
                              <Chip
                                key={l}
                                size="small"
                                label={l}
                                sx={{ height: 18, fontSize: 10 }}
                                variant="outlined"
                              />
                            ))}
                          </Stack>
                        </TableCell>
                        <TableCell>
                          {issue.already_linked ? (
                            <Chip
                              size="small"
                              label="Vinculado"
                              color="success"
                              sx={{ height: 20, fontSize: 11 }}
                            />
                          ) : (
                            <Chip
                              size="small"
                              label="—"
                              variant="outlined"
                              sx={{ height: 20, fontSize: 11 }}
                            />
                          )}
                        </TableCell>
                        <TableCell>
                          <MuiLink
                            href={issue.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            <ExternalLink size={14} />
                          </MuiLink>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Paper>

          {/* Links existentes */}
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            mb={2}
          >
            <Typography variant="subtitle1" fontWeight={600}>
              Links tarea ↔ issue
            </Typography>
            <Button
              variant="contained"
              size="small"
              startIcon={<Plus size={16} />}
              onClick={() => {
                setLinkForm({ taskId: "", repoId: "", issueNumber: "" });
                setLinkDialogOpen(true);
              }}
            >
              Nuevo link
            </Button>
          </Stack>

          {loadingLinks ? (
            <LoadingBox />
          ) : linkList.length === 0 ? (
            <EmptyState
              icon={<Link2 size={40} color="#ccc" />}
              message="No hay links creados. Crea uno para vincular una tarea con un issue de GitHub."
            />
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Task ID</TableCell>
                    <TableCell>Repo</TableCell>
                    <TableCell>Issue</TableCell>
                    <TableCell>Estado</TableCell>
                    <TableCell>Última sync</TableCell>
                    <TableCell>Acciones</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {linkList.map((link) => (
                    <TableRow key={link.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          #{link.task}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{link.repo_full_name}</Typography>
                      </TableCell>
                      <TableCell>
                        <Stack direction="row" alignItems="center" spacing={0.5}>
                          <Typography variant="body2" fontFamily="monospace">
                            #{link.issue_number}
                          </Typography>
                          <MuiLink
                            href={link.issue_url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            <ExternalLink size={12} />
                          </MuiLink>
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={link.issue_state}
                          sx={{
                            height: 20,
                            fontSize: 11,
                            bgcolor:
                              link.issue_state === "open"
                                ? "success.light"
                                : "grey.400",
                            color: "#fff",
                          }}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {link.last_synced_at
                            ? new Date(link.last_synced_at).toLocaleString("es-ES")
                            : "Nunca"}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Tooltip title="Sincronizar link">
                          <IconButton
                            size="small"
                            onClick={() => syncLinkMut.mutate(link.id)}
                            disabled={syncLinkMut.isPending}
                          >
                            <RefreshCw size={14} />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </TabPanel>
      </Paper>

      {/* ===== Dialog: Importar issues ===== */}
      <Dialog
        open={importDialogOpen}
        onClose={() => setImportDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Importar issues</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Alert severity="info">
              Se importarán los issues <strong>{issueState}</strong> del repo seleccionado
              como tareas. Las ya vinculadas se omitirán.
            </Alert>
            <TextField
              label="Filtro por label (opcional)"
              value={importLabel}
              onChange={(e) => setImportLabel(e.target.value)}
              fullWidth
              size="small"
              helperText="Ej: bug, enhancement. Déjalo vacío para importar todos."
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setImportDialogOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={() => importMut.mutate()}
            disabled={importMut.isPending}
          >
            {importMut.isPending ? "Importando..." : "Importar"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===== Dialog: Crear link ===== */}
      <Dialog
        open={linkDialogOpen}
        onClose={() => setLinkDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Crear link tarea ↔ issue</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="ID de la tarea"
              value={linkForm.taskId}
              onChange={(e) =>
                setLinkForm({ ...linkForm, taskId: e.target.value })
              }
              fullWidth
              size="small"
              type="number"
              helperText="Introduce el ID numérico de la tarea existente"
            />
            <FormControl fullWidth size="small">
              <InputLabel>Repositorio</InputLabel>
              <Select
                value={linkForm.repoId}
                label="Repositorio"
                onChange={(e) =>
                  setLinkForm({
                    ...linkForm,
                    repoId: e.target.value as number,
                  })
                }
              >
                <MenuItem value="">
                  <em>— Selecciona —</em>
                </MenuItem>
                {repoList.map((r) => (
                  <MenuItem key={r.id} value={r.id}>
                    {r.full_name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Número de issue"
              value={linkForm.issueNumber}
              onChange={(e) =>
                setLinkForm({ ...linkForm, issueNumber: e.target.value })
              }
              fullWidth
              size="small"
              type="number"
              helperText="Número del issue en GitHub (ej: 42)"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLinkDialogOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={() => createLinkMut.mutate()}
            disabled={
              createLinkMut.isPending ||
              !linkForm.taskId ||
              linkForm.repoId === ""
            }
          >
            {createLinkMut.isPending ? "Creando..." : "Crear link"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
