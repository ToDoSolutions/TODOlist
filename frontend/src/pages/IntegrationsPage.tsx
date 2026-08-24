import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Switch,
  IconButton,
  Alert,
  Stack,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Divider,
} from "@mui/material";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Github, RefreshCw, Trash2, Download, ExternalLink } from "lucide-react";
import { githubApi, type GitHubRepo, type GitHubIssue } from "../api/resources";
import { notify } from "../notify";

export default function IntegrationsPage() {
  const qc = useQueryClient();
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState<GitHubRepo | null>(null);
  const [issueState, setIssueState] = useState("open");

  const { data: installations = [], isLoading: loadingInst } = useQuery({
    queryKey: ["github-installations"],
    queryFn: githubApi.listInstallations,
  });

  const { data: repos = [], isLoading: loadingRepos } = useQuery({
    queryKey: ["github-repos"],
    queryFn: githubApi.listRepos,
  });

  const discoverMut = useMutation({
    mutationFn: githubApi.discoverRepos,
    onSuccess: (data) => {
      notify.success(data.message);
      qc.invalidateQueries({ queryKey: ["github-repos"] });
    },
    onError: (e: any) => notify.error(e.response?.data?.error || "Error"),
  });

  const toggleSyncMut = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      githubApi.updateRepo(id, { sync_enabled: enabled }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["github-repos"] });
      notify.info("Sincronización actualizada");
    },
  });

  const syncRepoMut = useMutation({
    mutationFn: githubApi.syncRepo,
    onSuccess: (data) => notify.success(data.message),
    onError: (e: any) => notify.error(e.response?.data?.error || "Error"),
  });

  const importMut = useMutation({
    mutationFn: ({ repoId, state }: { repoId: number; state: string }) =>
      githubApi.importIssues(repoId, state),
    onSuccess: (data) => {
      notify.success(`Importadas ${data.imported} issues (${data.skipped} ya existían)`);
      setImportDialogOpen(false);
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: (e: any) => notify.error(e.response?.data?.error || "Error al importar"),
  });

  const openImportDialog = (repo: GitHubRepo) => {
    setSelectedRepo(repo);
    setImportDialogOpen(true);
  };

  return (
    <Box maxWidth={800} mx="auto">
      <Typography variant="h5" fontWeight={700} mb={3}>
        Integraciones
      </Typography>

      {/* GitHub Connection Status */}
      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent>
          <Stack direction="row" alignItems="center" spacing={2} mb={2}>
            <Github size={28} />
            <Box flex={1}>
              <Typography variant="h6">GitHub</Typography>
              <Typography variant="body2" color="text.secondary">
                Sincroniza tareas con issues de GitHub
              </Typography>
            </Box>
            {installations.length > 0 ? (
              <Chip label="Conectado" color="success" size="small" />
            ) : (
              <Chip label="No conectado" color="default" size="small" />
            )}
          </Stack>

          {loadingInst ? (
            <CircularProgress size={20} />
          ) : installations.length > 0 ? (
            <>
              {installations.map((inst) => (
                <Box key={inst.id} sx={{ mb: 1 }}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    {inst.avatar_url && (
                      <img
                        src={inst.avatar_url}
                        alt={inst.account_login}
                        style={{ width: 20, height: 20, borderRadius: "50%" }}
                      />
                    )}
                    <Typography variant="body2">
                      {inst.account_login} ({inst.account_type})
                    </Typography>
                  </Stack>
                </Box>
              ))}
              <Button
                variant="outlined"
                size="small"
                startIcon={<RefreshCw size={16} />}
                onClick={() => discoverMut.mutate()}
                disabled={discoverMut.isPending}
                sx={{ mt: 1 }}
              >
                Descubrir repositorios
              </Button>
            </>
          ) : (
            <Alert severity="info" sx={{ mt: 1 }}>
              Conecta tu cuenta de GitHub desde la pantalla de login con "Sign in with GitHub"
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Repos sincronizados */}
      {repos.length > 0 && (
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" mb={2}>
              Repositorios sincronizados ({repos.length})
            </Typography>
            <List>
              {repos.map((repo) => (
                <ListItem
                  key={repo.id}
                  sx={{ borderBottom: "1px solid", borderColor: "divider" }}
                  secondaryAction={
                    <Stack direction="row" spacing={1} alignItems="center">
                      <IconButton
                        size="small"
                        onClick={() => syncRepoMut.mutate(repo.id)}
                        title="Sincronizar ahora"
                      >
                        <RefreshCw size={16} />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => openImportDialog(repo)}
                        title="Importar issues"
                      >
                        <Download size={16} />
                      </IconButton>
                      <Switch
                        size="small"
                        checked={repo.sync_enabled}
                        onChange={(e) =>
                          toggleSyncMut.mutate({
                            id: repo.id,
                            enabled: e.target.checked,
                          })
                        }
                      />
                    </Stack>
                  }
                >
                  <ListItemIcon>
                    <Github size={20} />
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <Typography variant="body2" fontWeight={600}>
                          {repo.full_name}
                        </Typography>
                        {repo.is_private && (
                          <Chip label="Private" size="small" sx={{ height: 16, fontSize: 10 }} />
                        )}
                      </Stack>
                    }
                    secondary={`Branch: ${repo.default_branch}`}
                  />
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      )}

      {/* Dialog de importar issues */}
      <Dialog open={importDialogOpen} onClose={() => setImportDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          Importar issues de {selectedRepo?.full_name}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" mb={2}>
            Selecciona el estado de los issues a importar:
          </Typography>
          <Stack direction="row" spacing={1}>
            {["open", "closed", "all"].map((s) => (
              <Chip
                key={s}
                label={s === "open" ? "Abiertos" : s === "closed" ? "Cerrados" : "Todos"}
                color={issueState === s ? "primary" : "default"}
                onClick={() => setIssueState(s)}
              />
            ))}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setImportDialogOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={() =>
              selectedRepo && importMut.mutate({ repoId: selectedRepo.id, state: issueState })
            }
            disabled={importMut.isPending}
            startIcon={importMut.isPending ? <CircularProgress size={16} /> : <Download size={16} />}
          >
            Importar
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
