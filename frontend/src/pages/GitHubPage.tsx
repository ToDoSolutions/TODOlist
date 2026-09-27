import { formatDateTime, formatDate, formatTime } from "../lib/dates";
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
  useTheme,
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
  GitPullRequest,
  GitCommit,
  Tag,
  CheckCircle,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  githubApi,
  tasksApi,
  type GitHubInstallation,
  type GitHubRepo,
  type GitHubIssue,
  type GitHubIssueLink,
} from "../api/resources";
import type { GitHubPR, GitHubCommit, GitHubRelease, GitHubCheckRun } from "../types";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import { useTranslation, Trans } from "react-i18next";

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
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();
  const confirm = useConfirm();
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
        data.message ||
          t("p.integr.ghDiscoverSuccess", { new: data.new, total: data.total }),
      );
      qc.invalidateQueries({ queryKey: ["github-repos"] });
      qc.invalidateQueries({ queryKey: ["github-installations"] });
    },
    onError: () => notify.error(t("p.integr.ghDiscoverError")),
  });

  const removeInstMut = useMutation({
    mutationFn: githubApi.removeInstallation,
    onSuccess: () => {
      notify.info(t("p.integr.ghInstDeleted"));
      qc.invalidateQueries({ queryKey: ["github-installations"] });
      qc.invalidateQueries({ queryKey: ["github-repos"] });
    },
    onError: () => notify.error(t("p.integr.ghInstDeleteError")),
  });

  /* ----- Repos ----- */
  const { data: repos, isLoading: loadingRepos } = useQuery({
    queryKey: ["github-repos"],
    queryFn: githubApi.listRepos,
  });

  const syncRepoMut = useMutation({
    mutationFn: githubApi.syncRepo,
    onSuccess: (data) => {
      notify.success(data.message || t("p.integr.ghRepoSynced"));
      qc.invalidateQueries({ queryKey: ["github-repos"] });
    },
    onError: () => notify.error(t("p.integr.ghRepoSyncError")),
  });

  const updateRepoMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<GitHubRepo> }) =>
      githubApi.updateRepo(id, data),
    onSuccess: () => {
      notify.success(t("p.integr.ghRepoUpdated"));
      qc.invalidateQueries({ queryKey: ["github-repos"] });
    },
    onError: () => notify.error(t("p.integr.ghRepoUpdateError")),
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

  /* ----- PRs, Commits, Releases, CI ----- */
  const { data: pullRequests, isLoading: loadingPRs } = useQuery({
    queryKey: ["github-pull-requests"],
    queryFn: githubApi.listPullRequests,
  });

  const { data: commits, isLoading: loadingCommits } = useQuery({
    queryKey: ["github-commits"],
    queryFn: githubApi.listCommits,
  });

  const { data: releases, isLoading: loadingReleases } = useQuery({
    queryKey: ["github-releases"],
    queryFn: githubApi.listReleases,
  });

  const { data: checks, isLoading: loadingChecks } = useQuery({
    queryKey: ["github-checks"],
    queryFn: githubApi.listChecks,
  });

  const importMut = useMutation({
    mutationFn: () =>
      githubApi.importIssues(selectedRepoId as number, issueState, importLabel),
    onSuccess: (data) => {
      notify.success(
        t("p.integr.ghImportSuccess", {
          imported: data.imported,
          skipped: data.skipped,
          total: data.total,
        }),
      );
      setImportDialogOpen(false);
      setImportLabel("");
      qc.invalidateQueries({ queryKey: ["github-links"] });
    },
    onError: () => notify.error(t("p.integr.ghImportError")),
  });

  const createLinkMut = useMutation({
    mutationFn: () =>
      githubApi.createLinkForTask(Number(linkForm.taskId), Number(linkForm.repoId)),
    onSuccess: () => {
      notify.success(t("p.integr.ghLinkCreated"));
      setLinkDialogOpen(false);
      setLinkForm({ taskId: "", repoId: "", issueNumber: "" });
      qc.invalidateQueries({ queryKey: ["github-links"] });
    },
    onError: () => notify.error(t("p.integr.ghLinkCreateError")),
  });

  const syncLinkMut = useMutation({
    mutationFn: githubApi.syncLink,
    onSuccess: (data) => {
      notify.success(data.message || t("p.integr.ghLinkSynced"));
      qc.invalidateQueries({ queryKey: ["github-links"] });
    },
    onError: () => notify.error(t("p.integr.ghLinkSyncError")),
  });

  const instList: GitHubInstallation[] = Array.isArray(installations)
    ? installations
    : (installations as { results?: GitHubInstallation[] } | undefined)?.results || [];
  const repoList: GitHubRepo[] = Array.isArray(repos)
    ? repos
    : (repos as { results?: GitHubRepo[] } | undefined)?.results || [];
  const issueList: GitHubIssue[] = Array.isArray(issues)
    ? issues
    : (issues as { results?: GitHubIssue[] } | undefined)?.results || [];
  const linkList: GitHubIssueLink[] = Array.isArray(links)
    ? links
    : (links as { results?: GitHubIssueLink[] } | undefined)?.results || [];

  const prList: GitHubPR[] = Array.isArray(pullRequests)
    ? pullRequests
    : (pullRequests as { results?: GitHubPR[] } | undefined)?.results || [];
  const commitList: GitHubCommit[] = Array.isArray(commits)
    ? commits
    : (commits as { results?: GitHubCommit[] } | undefined)?.results || [];
  const releaseList: GitHubRelease[] = Array.isArray(releases)
    ? releases
    : (releases as { results?: GitHubRelease[] } | undefined)?.results || [];
  const checkList: GitHubCheckRun[] = Array.isArray(checks)
    ? checks
    : (checks as { results?: GitHubCheckRun[] } | undefined)?.results || [];

  const { data: tasksData } = useQuery({
    queryKey: ["tasks-for-github-links"],
    queryFn: () => tasksApi.list(),
  });
  const taskTitleMap = new Map(
    (Array.isArray(tasksData)
      ? tasksData
      : (tasksData as { results?: { id: number; title: string }[] } | undefined)
          ?.results || []
    ).map((task) => [task.id, task.title]),
  );

  /* ---------- render ---------- */

  return (
    <Box maxWidth={1000} mx="auto">
      <Stack direction="row" alignItems="center" spacing={1} mb={3}>
        <Github size={28} style={{ color: theme.palette.primary.main }} />
        <Typography variant="h5" fontWeight={700}>
          {t("p.integr.ghTitle")}
        </Typography>
      </Stack>

      <Alert severity="info" sx={{ mb: 2 }}>
        {t("p.integr.ghIntro")}
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
            label={t("p.integr.ghTabInstallations")}
          />
          <Tab label={t("p.integr.ghTabRepos")} />
          <Tab
            icon={<Link2 size={16} />}
            iconPosition="start"
            label={t("p.integr.ghTabIssuesLinks")}
          />
          <Tab
            icon={<GitPullRequest size={16} />}
            iconPosition="start"
            label={t("p.integr.ghTabPrs")}
          />
          <Tab
            icon={<GitCommit size={16} />}
            iconPosition="start"
            label={t("p.integr.ghTabCommits")}
          />
          <Tab
            icon={<Tag size={16} />}
            iconPosition="start"
            label={t("p.integr.ghTabReleases")}
          />
          <Tab
            icon={<CheckCircle size={16} />}
            iconPosition="start"
            label={t("p.integr.ci")}
          />
        </Tabs>

        {/* ===== Tab 1: Instalaciones ===== */}
        <TabPanel value={tab} index={0}>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            mb={2}
          >
            <Typography variant="subtitle1" fontWeight={600}>
              {t("p.integr.ghInstTitle")}
            </Typography>
            <Button
              variant="contained"
              size="small"
              startIcon={<RefreshCw size={16} />}
              onClick={() => discoverMut.mutate()}
              disabled={discoverMut.isPending}
            >
              {discoverMut.isPending
                ? t("p.integr.ghDiscovering")
                : t("p.integr.ghDiscover")}
            </Button>
          </Stack>

          {loadingInst ? (
            <LoadingBox />
          ) : instList.length === 0 ? (
            <EmptyState
              icon={<Github size={48} color="text.disabled" />}
              message={t("p.integr.ghInstEmpty")}
            />
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t("p.integr.ghColAccount")}</TableCell>
                    <TableCell>{t("p.integr.type")}</TableCell>
                    <TableCell>{t("p.integr.user")}</TableCell>
                    <TableCell>{t("p.integr.ghColInstId")}</TableCell>
                    <TableCell>{t("p.integr.ghColCreated")}</TableCell>
                    <TableCell>{t("p.integr.actions")}</TableCell>
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
                          {formatDate(inst.created_at)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Tooltip title={t("p.integr.ghInstRemoveTooltip")}>
                          <IconButton
                            size="small"
                            color="error"
                            onClick={async () => {
                              if (
                                await confirm(
                                  t("p.integr.ghInstConfirmDisconnect", {
                                    account: inst.account_login || "GitHub",
                                  }),
                                )
                              )
                                removeInstMut.mutate(inst.id);
                            }}
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
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            mb={2}
          >
            <Typography variant="subtitle1" fontWeight={600}>
              {t("p.integr.ghReposTitle")}
            </Typography>
            <Button
              variant="outlined"
              size="small"
              startIcon={<RefreshCw size={16} />}
              onClick={() => qc.invalidateQueries({ queryKey: ["github-repos"] })}
            >
              {t("p.integr.refresh")}
            </Button>
          </Stack>

          {loadingRepos ? (
            <LoadingBox />
          ) : repoList.length === 0 ? (
            <EmptyState
              icon={<Github size={48} color="text.disabled" />}
              message={t("p.integr.ghReposEmpty")}
            />
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t("p.integr.ghRepo")}</TableCell>
                    <TableCell>{t("p.integr.ghColOwner")}</TableCell>
                    <TableCell>{t("p.integr.ghColBranch")}</TableCell>
                    <TableCell>{t("p.integr.ghColVisibility")}</TableCell>
                    <TableCell>{t("p.integr.ghColSync")}</TableCell>
                    <TableCell>{t("p.integr.actions")}</TableCell>
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
                          label={
                            repo.is_private
                              ? t("p.integr.ghPrivate")
                              : t("p.integr.ghPublic")
                          }
                          sx={{
                            height: 20,
                            fontSize: 11,
                            bgcolor: repo.is_private ? "warning.light" : "success.light",
                            color: "common.white",
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
                            {repo.sync_enabled
                              ? t("p.integr.ghSyncOn")
                              : t("p.integr.ghSyncOff")}
                          </Typography>
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Tooltip title={t("p.integr.ghSyncRepoTooltip")}>
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
                <InputLabel>{t("p.integr.ghSelectRepo")}</InputLabel>
                <Select
                  value={selectedRepoId}
                  label={t("p.integr.ghSelectRepo")}
                  onChange={(e) => setSelectedRepoId(e.target.value as number)}
                >
                  <MenuItem value="">
                    <em>{t("p.integr.ghNone")}</em>
                  </MenuItem>
                  {repoList.map((r) => (
                    <MenuItem key={r.id} value={r.id}>
                      {r.full_name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel>{t("p.integr.status")}</InputLabel>
                <Select
                  value={issueState}
                  label={t("p.integr.status")}
                  onChange={(e) => setIssueState(e.target.value as string)}
                >
                  <MenuItem value="open">{t("p.integr.ghStateOpen")}</MenuItem>
                  <MenuItem value="closed">{t("p.integr.ghStateClosed")}</MenuItem>
                  <MenuItem value="all">{t("p.integr.ghStateAll")}</MenuItem>
                </Select>
              </FormControl>
              <Button
                variant="contained"
                size="small"
                startIcon={<Download size={16} />}
                onClick={() => setImportDialogOpen(true)}
                disabled={selectedRepoId === ""}
              >
                {t("p.integr.ghImportIssues")}
              </Button>
            </Stack>

            {selectedRepoId === "" ? (
              <Alert severity="info">{t("p.integr.ghSelectRepoHint")}</Alert>
            ) : loadingIssues ? (
              <LoadingBox />
            ) : issueList.length === 0 ? (
              <EmptyState
                icon={<Github size={40} color="text.disabled" />}
                message={t("p.integr.ghIssuesEmpty")}
              />
            ) : (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell width={60}>#</TableCell>
                      <TableCell>{t("p.integr.title")}</TableCell>
                      <TableCell>{t("p.integr.status")}</TableCell>
                      <TableCell>{t("p.integr.ghColLabels")}</TableCell>
                      <TableCell>{t("p.integr.ghColLink")}</TableCell>
                      <TableCell>{t("p.integr.url")}</TableCell>
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
                              color: "common.white",
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
                              label={t("p.integr.ghLinked")}
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
              {t("p.integr.ghLinksTitle")}
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
              {t("p.integr.ghNewLink")}
            </Button>
          </Stack>

          {loadingLinks ? (
            <LoadingBox />
          ) : linkList.length === 0 ? (
            <EmptyState
              icon={<Link2 size={40} color="text.disabled" />}
              message={t("p.integr.ghLinksEmpty")}
            />
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t("p.integr.ghColTaskId")}</TableCell>
                    <TableCell>{t("p.integr.repo")}</TableCell>
                    <TableCell>{t("p.integr.ghColIssue")}</TableCell>
                    <TableCell>{t("p.integr.status")}</TableCell>
                    <TableCell>{t("p.integr.ghColLastSync")}</TableCell>
                    <TableCell>{t("p.integr.actions")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {linkList.map((link) => (
                    <TableRow key={link.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          #{link.task}
                        </Typography>
                        {taskTitleMap.has(link.task) && (
                          <Typography variant="caption" color="text.secondary">
                            {String(taskTitleMap.get(link.task))}
                          </Typography>
                        )}
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
                              link.issue_state === "open" ? "success.light" : "grey.400",
                            color: "common.white",
                          }}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {link.last_synced_at
                            ? formatDateTime(link.last_synced_at)
                            : t("p.integr.never")}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Tooltip title={t("p.integr.ghSyncLinkTooltip")}>
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

        {/* ===== Tab 4: PRs ===== */}
        <TabPanel value={tab} index={3}>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            mb={2}
          >
            <Typography variant="subtitle1" fontWeight={600}>
              {t("p.integr.ghPrsTitle")}
            </Typography>
            <Button
              variant="outlined"
              size="small"
              startIcon={<RefreshCw size={16} />}
              onClick={() => qc.invalidateQueries({ queryKey: ["github-pull-requests"] })}
            >
              {t("p.integr.refresh")}
            </Button>
          </Stack>

          {loadingPRs ? (
            <LoadingBox />
          ) : prList.length === 0 ? (
            <EmptyState
              icon={<GitPullRequest size={40} color="text.disabled" />}
              message={t("p.integr.ghPrsEmpty")}
            />
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell width={60}>PR#</TableCell>
                    <TableCell>{t("p.integr.title")}</TableCell>
                    <TableCell>{t("p.integr.status")}</TableCell>
                    <TableCell>{t("p.integr.author")}</TableCell>
                    <TableCell>{t("p.integr.ghColBranch")}</TableCell>
                    <TableCell>{t("p.integr.ghColApprovals")}</TableCell>
                    <TableCell>{t("p.integr.ci")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {prList.map((pr) => {
                    const stateLabel = pr.is_merged
                      ? "merged"
                      : pr.state === "open"
                        ? "open"
                        : "closed";
                    const stateColor =
                      stateLabel === "merged"
                        ? "secondary.light"
                        : stateLabel === "open"
                          ? "success.light"
                          : "grey.400";
                    return (
                      <TableRow key={pr.pr_number}>
                        <TableCell>
                          <Typography variant="body2" fontFamily="monospace">
                            #{pr.pr_number}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <MuiLink
                            href={pr.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {pr.title}
                          </MuiLink>
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            label={stateLabel}
                            sx={{
                              height: 20,
                              fontSize: 11,
                              bgcolor: stateColor,
                              color: "common.white",
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{pr.author}</Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption" color="text.secondary">
                            {pr.head_branch} → {pr.base_branch}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            label={pr.approvals_count ?? 0}
                            sx={{ height: 20, fontSize: 11 }}
                            variant="outlined"
                          />
                        </TableCell>
                        <TableCell>
                          {pr.ci_status ? (
                            <Chip
                              size="small"
                              label={pr.ci_status}
                              sx={{
                                height: 20,
                                fontSize: 11,
                                bgcolor:
                                  pr.ci_status === "success"
                                    ? "success.light"
                                    : pr.ci_status === "failure"
                                      ? "error.light"
                                      : "grey.400",
                                color: "common.white",
                              }}
                            />
                          ) : (
                            <Typography variant="caption" color="text.secondary">
                              —
                            </Typography>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </TabPanel>

        {/* ===== Tab 5: Commits ===== */}
        <TabPanel value={tab} index={4}>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            mb={2}
          >
            <Typography variant="subtitle1" fontWeight={600}>
              {t("p.integr.ghCommitsTitle")}
            </Typography>
            <Button
              variant="outlined"
              size="small"
              startIcon={<RefreshCw size={16} />}
              onClick={() => qc.invalidateQueries({ queryKey: ["github-commits"] })}
            >
              {t("p.integr.refresh")}
            </Button>
          </Stack>

          {loadingCommits ? (
            <LoadingBox />
          ) : commitList.length === 0 ? (
            <EmptyState
              icon={<GitCommit size={40} color="text.disabled" />}
              message={t("p.integr.ghCommitsEmpty")}
            />
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell width={100}>SHA</TableCell>
                    <TableCell>{t("p.integr.ghColMessage")}</TableCell>
                    <TableCell>{t("p.integr.author")}</TableCell>
                    <TableCell>{t("p.integr.date")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {commitList.map((c) => (
                    <TableRow key={c.sha}>
                      <TableCell>
                        <MuiLink
                          href={c.html_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          sx={{ fontFamily: "monospace" }}
                        >
                          {c.sha}
                        </MuiLink>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {c.message?.split("\n")[0]}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{c.author}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {c.author_date ? formatDateTime(c.author_date) : "—"}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </TabPanel>

        {/* ===== Tab 6: Releases ===== */}
        <TabPanel value={tab} index={5}>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            mb={2}
          >
            <Typography variant="subtitle1" fontWeight={600}>
              {t("p.integr.ghReleasesTitle")}
            </Typography>
            <Button
              variant="outlined"
              size="small"
              startIcon={<RefreshCw size={16} />}
              onClick={() => qc.invalidateQueries({ queryKey: ["github-releases"] })}
            >
              {t("p.integr.refresh")}
            </Button>
          </Stack>

          {loadingReleases ? (
            <LoadingBox />
          ) : releaseList.length === 0 ? (
            <EmptyState
              icon={<Tag size={40} color="text.disabled" />}
              message={t("p.integr.ghReleasesEmpty")}
            />
          ) : (
            <Stack spacing={2}>
              {releaseList.map((r) => (
                <Paper key={r.tag_name} variant="outlined" sx={{ p: 2 }}>
                  <Stack
                    direction="row"
                    alignItems="center"
                    spacing={1}
                    mb={1}
                    flexWrap="wrap"
                  >
                    <Chip
                      size="small"
                      label={r.tag_name}
                      sx={{ height: 22, fontSize: 12, fontWeight: 600 }}
                      color="primary"
                    />
                    {r.is_prerelease && (
                      <Chip
                        size="small"
                        label={t("p.integr.ghPrerelease")}
                        sx={{
                          height: 20,
                          fontSize: 11,
                          bgcolor: "warning.light",
                          color: "common.white",
                        }}
                      />
                    )}
                    <Typography variant="subtitle2" fontWeight={600}>
                      {r.name}
                    </Typography>
                    <MuiLink href={r.html_url} target="_blank" rel="noopener noreferrer">
                      <ExternalLink size={14} />
                    </MuiLink>
                  </Stack>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      display: "-webkit-box",
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {r.body || t("p.integr.ghNoDescription")}
                  </Typography>
                  <Stack direction="row" spacing={2} mt={1}>
                    <Typography variant="caption" color="text.secondary">
                      {t("p.integr.ghAuthorLine", { author: r.author || "—" })}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {t("p.integr.ghPublishedLine", {
                        date: r.published_at ? formatDateTime(r.published_at) : "—",
                      })}
                    </Typography>
                  </Stack>
                </Paper>
              ))}
            </Stack>
          )}
        </TabPanel>

        {/* ===== Tab 7: CI ===== */}
        <TabPanel value={tab} index={6}>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            mb={2}
          >
            <Typography variant="subtitle1" fontWeight={600}>
              {t("p.integr.ghCiTitle")}
            </Typography>
            <Button
              variant="outlined"
              size="small"
              startIcon={<RefreshCw size={16} />}
              onClick={() => qc.invalidateQueries({ queryKey: ["github-checks"] })}
            >
              {t("p.integr.refresh")}
            </Button>
          </Stack>

          {loadingChecks ? (
            <LoadingBox />
          ) : checkList.length === 0 ? (
            <EmptyState
              icon={<CheckCircle size={40} color="text.disabled" />}
              message={t("p.integr.ghCiEmpty")}
            />
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t("p.integr.ghColName")}</TableCell>
                    <TableCell>{t("p.integr.status")}</TableCell>
                    <TableCell>{t("p.integr.ghColConclusion")}</TableCell>
                    <TableCell>{t("p.integr.ghColDuration")}</TableCell>
                    <TableCell>{t("p.integr.url")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {checkList.map((c, i) => {
                    const statusLabel =
                      c.status === "in_progress"
                        ? "in_progress"
                        : c.status === "queued"
                          ? "queued"
                          : "completed";
                    const statusColor =
                      statusLabel === "completed"
                        ? "success.light"
                        : statusLabel === "in_progress"
                          ? "warning.light"
                          : "grey.400";
                    const conclusionLabel = c.conclusion || "—";
                    const conclusionColor =
                      c.conclusion === "success"
                        ? "success.light"
                        : c.conclusion === "failure"
                          ? "error.light"
                          : "grey.400";
                    const duration =
                      c.started_at && c.completed_at
                        ? `${formatTime(c.started_at)} → ${formatTime(c.completed_at)}`
                        : c.started_at
                          ? formatDateTime(c.started_at)
                          : "—";
                    return (
                      <TableRow key={i}>
                        <TableCell>
                          <Typography variant="body2">{c.name}</Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            label={statusLabel}
                            sx={{
                              height: 20,
                              fontSize: 11,
                              bgcolor: statusColor,
                              color: "common.white",
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          {c.conclusion ? (
                            <Chip
                              size="small"
                              label={conclusionLabel}
                              sx={{
                                height: 20,
                                fontSize: 11,
                                bgcolor: conclusionColor,
                                color: "common.white",
                              }}
                            />
                          ) : (
                            <Typography variant="caption" color="text.secondary">
                              —
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption" color="text.secondary">
                            {duration}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <MuiLink
                            href={c.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            <ExternalLink size={14} />
                          </MuiLink>
                        </TableCell>
                      </TableRow>
                    );
                  })}
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
        <DialogTitle>{t("p.integr.ghImportIssues")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Alert severity="info">
              <Trans i18nKey="p.integr.ghImportInfo" values={{ state: issueState }} />
            </Alert>
            <TextField
              label={t("p.integr.ghLabelFilter")}
              value={importLabel}
              onChange={(e) => setImportLabel(e.target.value)}
              fullWidth
              size="small"
              helperText={t("p.integr.ghLabelFilterHelp")}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setImportDialogOpen(false)}>
            {t("p.integr.cancel")}
          </Button>
          <Button
            variant="contained"
            onClick={() => importMut.mutate()}
            disabled={importMut.isPending}
          >
            {importMut.isPending ? t("p.integr.ghImporting") : t("p.integr.ghImport")}
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
        <DialogTitle>{t("p.integr.ghLinkDialogTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("p.integr.ghTaskIdLabel")}
              value={linkForm.taskId}
              onChange={(e) => setLinkForm({ ...linkForm, taskId: e.target.value })}
              fullWidth
              size="small"
              type="number"
              helperText={t("p.integr.ghTaskIdHelp")}
            />
            <FormControl fullWidth size="small">
              <InputLabel>{t("p.integr.ghRepo")}</InputLabel>
              <Select
                value={linkForm.repoId}
                label={t("p.integr.ghRepo")}
                onChange={(e) =>
                  setLinkForm({
                    ...linkForm,
                    repoId: e.target.value as number,
                  })
                }
              >
                <MenuItem value="">
                  <em>{t("p.integr.ghSelect")}</em>
                </MenuItem>
                {repoList.map((r) => (
                  <MenuItem key={r.id} value={r.id}>
                    {r.full_name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label={t("p.integr.ghIssueNumber")}
              value={linkForm.issueNumber}
              onChange={(e) => setLinkForm({ ...linkForm, issueNumber: e.target.value })}
              fullWidth
              size="small"
              type="number"
              helperText={t("p.integr.ghIssueNumberHelp")}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLinkDialogOpen(false)}>{t("p.integr.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => createLinkMut.mutate()}
            disabled={
              createLinkMut.isPending || !linkForm.taskId || linkForm.repoId === ""
            }
          >
            {createLinkMut.isPending
              ? t("p.integr.ghCreating")
              : t("p.integr.ghCreateLink")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
