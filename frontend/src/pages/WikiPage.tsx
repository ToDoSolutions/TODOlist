import { lazy, Suspense, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { TaskListSkeleton } from "../components/ui/skeletons";
import PageHeader from "../components/ui/PageHeader";
import { ErrorState } from "../components/ui/states";

// Editor markdown con toolbar y preview en vivo (bundle pesado → lazy)
const MDEditor = lazy(() => import("@uiw/react-md-editor"));
import {
  Box,
  Typography,
  Stack,
  Button,
  Paper,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  CircularProgress,
  IconButton,
  MenuItem,
} from "@mui/material";
import { Plus, FileText, Pencil, Trash2, History, RotateCcw } from "lucide-react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useTheme } from "@mui/material/styles";
import { useThemeMode } from "../theme-context";
import {
  projectsApi,
  wikiApi,
  type WikiPageItem,
  type ApiPayload,
} from "../api/resources";
import { formatDateTime } from "../lib/dates";
import type { Project } from "../types";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";

export default function WikiPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { mode: themeMode } = useThemeMode();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<WikiPageItem | null>(null);
  const [viewing, setViewing] = useState<WikiPageItem | null>(null);
  const [historyFor, setHistoryFor] = useState<WikiPageItem | null>(null);
  const [previewRev, setPreviewRev] = useState<number | null>(null);
  const [form, setForm] = useState({
    title: "",
    content: "",
    project: "" as string | number,
  });

  const {
    data: pages = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["wiki"],
    queryFn: wikiApi.list,
  });
  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData)
    ? projectsData
    : (projectsData as { results?: Project[] } | undefined)?.results || [];
  const projectMap = new Map<number, string>(
    projects.map((p) => [p.id, p.name] as [number, string]),
  );

  const saveMut = useMutation({
    mutationFn: () => {
      const payload: ApiPayload = {
        title: form.title.trim(),
        content: form.content,
        project: form.project || null,
      };
      return editing ? wikiApi.update(editing.id, payload) : wikiApi.create(payload);
    },
    onSuccess: () => {
      notify.success(editing ? t("p.collab.wiki.updated") : t("p.collab.wiki.created"));
      qc.invalidateQueries({ queryKey: ["wiki"] });
      setDialogOpen(false);
    },
    onError: () => notify.error(t("p.collab.wiki.saveError")),
  });

  const removeMut = useMutation({
    mutationFn: (id: number) => wikiApi.remove(id),
    onSuccess: () => {
      notify.success(t("p.collab.wiki.deleted"));
      qc.invalidateQueries({ queryKey: ["wiki"] });
    },
  });

  const { data: revisions = [], isLoading: loadingRevs } = useQuery({
    queryKey: ["wiki-revisions", historyFor?.id],
    queryFn: () => wikiApi.revisions(historyFor!.id),
    enabled: historyFor !== null,
  });

  const { data: revDetail } = useQuery({
    queryKey: ["wiki-rev-detail", historyFor?.id, previewRev],
    queryFn: () => wikiApi.revisionDetail(historyFor!.id, previewRev!),
    enabled: historyFor !== null && previewRev !== null,
  });

  const restoreMut = useMutation({
    mutationFn: (version: number) => wikiApi.restore(historyFor!.id, version),
    onSuccess: () => {
      notify.success(t("p.collab.wiki.restored"));
      qc.invalidateQueries({ queryKey: ["wiki"] });
      qc.invalidateQueries({ queryKey: ["wiki-revisions", historyFor?.id] });
      setPreviewRev(null);
    },
    onError: () => notify.error(t("p.collab.wiki.restoreError")),
  });

  const openNew = () => {
    setEditing(null);
    setForm({ title: "", content: "", project: "" });
    setDialogOpen(true);
  };
  const openEdit = (p: WikiPageItem) => {
    setEditing(p);
    setForm({ title: p.title, content: p.content, project: p.project || "" });
    setDialogOpen(true);
  };

  // Árbol: páginas raíz primero, hijos indentados
  const roots = pages.filter((p) => !p.parent);
  const childrenOf = (id: number) => pages.filter((p) => p.parent === id);

  const renderPage = (p: WikiPageItem, depth = 0) => (
    <Box key={p.id}>
      <Stack
        direction="row"
        alignItems="center"
        spacing={1.5}
        sx={{
          py: 1,
          px: 1.5,
          ml: depth * 3,
          borderRadius: 1.5,
          "&:hover": { bgcolor: "action.hover" },
        }}
      >
        <Box sx={{ color: "text.secondary", display: "flex" }}>
          <FileText size={16} />
        </Box>
        <Typography
          variant="body2"
          fontWeight={600}
          sx={{ flex: 1, cursor: "pointer", "&:hover": { color: "primary.main" } }}
          onClick={() => setViewing(p)}
        >
          {p.title}
        </Typography>
        {p.project && projectMap.get(p.project) && (
          <Chip
            label={String(projectMap.get(p.project))}
            size="small"
            variant="outlined"
          />
        )}
        <Typography variant="caption" color="text.secondary">
          v{p.version}
          {p.updated_by_email ? ` · ${p.updated_by_email}` : ""}
        </Typography>
        <IconButton
          size="small"
          title={t("p.collab.wiki.history")}
          onClick={() => {
            setHistoryFor(p);
            setPreviewRev(null);
          }}
        >
          <History size={14} />
        </IconButton>
        <IconButton size="small" onClick={() => openEdit(p)} aria-label={t("common.edit")}>
          <Pencil size={14} />
        </IconButton>
        <IconButton
          size="small"
          color="error"
          aria-label={t("common.delete")}
          onClick={async () => {
            if (
              await confirm(
                p.children_count
                  ? t("p.collab.wiki.confirmDeleteChildren", {
                      title: p.title,
                      count: p.children_count,
                    })
                  : t("p.collab.wiki.confirmDelete", { title: p.title }),
                { confirmLabel: t("p.collab.wiki.deletePage") },
              )
            ) {
              removeMut.mutate(p.id);
            }
          }}
        >
          <Trash2 size={14} />
        </IconButton>
      </Stack>
      {childrenOf(p.id).map((c) => renderPage(c, depth + 1))}
    </Box>
  );

  return (
    <Box maxWidth={800} mx="auto">
      <PageHeader
        title={t("p.collab.wiki.title")}
        description={t("p.collab.wiki.subtitle")}
        actions={
          <Button variant="contained" startIcon={<Plus size={18} />} onClick={openNew}>
            {t("p.collab.wiki.newPage")}
          </Button>
        }
      />

      {isError && (
        <ErrorState
          title={t("p.collab.wiki.loadError")}
          onRetry={() => void refetch()}
        />
      )}
      {isLoading ? (
        <TaskListSkeleton />
      ) : pages.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <FileText size={36} style={{ color: theme.palette.divider }} />
          <Typography color="text.secondary" mt={1}>
            {t("p.collab.wiki.empty")}
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={0.5}>{roots.map((p) => renderPage(p))}</Stack>
      )}

      {/* Vista lectura — markdown renderizado */}
      <Dialog open={!!viewing} onClose={() => setViewing(null)} fullWidth maxWidth="md">
        {viewing && (
          <>
            <DialogTitle>
              <Stack direction="row" alignItems="center" spacing={1}>
                <FileText size={18} />
                {viewing.title}
                <Chip label={`v${viewing.version}`} size="small" variant="outlined" />
              </Stack>
            </DialogTitle>
            <DialogContent dividers>
              <Box
                sx={{
                  "& h1": { fontSize: "1.75rem", mt: 0 },
                  "& h2": { fontSize: "1.4rem" },
                  "& h3": { fontSize: "1.15rem" },
                  "& code": {
                    bgcolor: "action.hover",
                    px: 0.5,
                    borderRadius: 0.5,
                    fontSize: "0.85em",
                  },
                  "& pre": {
                    bgcolor: "action.hover",
                    p: 1.5,
                    borderRadius: 1.5,
                    overflowX: "auto",
                  },
                  "& pre code": { bgcolor: "transparent", p: 0 },
                  "& blockquote": {
                    borderLeft: 3,
                    borderColor: "divider",
                    m: 0,
                    pl: 2,
                    color: "text.secondary",
                  },
                  "& table": { borderCollapse: "collapse" },
                  "& td, & th": { border: 1, borderColor: "divider", px: 1, py: 0.5 },
                  "& img": { maxWidth: "100%" },
                }}
              >
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    code({ className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || "");
                      const text = String(children).replace(/\n$/, "");
                      return match ? (
                        <SyntaxHighlighter
                          style={themeMode === "dark" ? oneDark : oneLight}
                          language={match[1]}
                          PreTag="div"
                          customStyle={{ borderRadius: 8, fontSize: "0.8rem" }}
                        >
                          {text}
                        </SyntaxHighlighter>
                      ) : (
                        <code className={className} {...props}>
                          {children}
                        </code>
                      );
                    },
                  }}
                >
                  {viewing.content || t("p.collab.wiki.noContent")}
                </ReactMarkdown>
              </Box>
            </DialogContent>
            <DialogActions>
              <Button
                startIcon={<History size={14} />}
                onClick={() => {
                  setHistoryFor(viewing);
                  setPreviewRev(null);
                }}
              >
                {t("p.collab.wiki.history")}
              </Button>
              <Button onClick={() => setViewing(null)}>{t("common.close")}</Button>
              <Button
                variant="contained"
                startIcon={<Pencil size={14} />}
                onClick={() => {
                  setViewing(null);
                  openEdit(viewing);
                }}
              >
                {t("common.edit")}
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>

      {/* Historial de revisiones */}
      <Dialog
        open={!!historyFor}
        onClose={() => setHistoryFor(null)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1}>
            <History size={18} />
            {t("p.collab.wiki.historyTitle", { title: historyFor?.title })}
          </Stack>
        </DialogTitle>
        <DialogContent dividers>
          {loadingRevs ? (
            <Box display="flex" justifyContent="center" py={4}>
              <CircularProgress />
            </Box>
          ) : revisions.length === 0 ? (
            <Typography color="text.secondary" py={2}>
              {t("p.collab.wiki.historyEmpty")}
            </Typography>
          ) : (
            <Stack spacing={0.5}>
              {revisions.map((r) => (
                <Stack
                  key={r.version}
                  direction="row"
                  alignItems="center"
                  spacing={1.5}
                  sx={{
                    py: 0.75,
                    px: 1.5,
                    borderRadius: 1.5,
                    bgcolor:
                      previewRev === r.version ? "action.selected" : undefined,
                    "&:hover": { bgcolor: "action.hover" },
                  }}
                >
                  <Chip label={`v${r.version}`} size="small" variant="outlined" />
                  <Typography
                    variant="body2"
                    sx={{ flex: 1, cursor: "pointer" }}
                    onClick={() =>
                      setPreviewRev(previewRev === r.version ? null : r.version)
                    }
                  >
                    {r.title}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatDateTime(r.created_at)}
                  </Typography>
                  <IconButton
                    size="small"
                    title={t("p.collab.wiki.restore")}
                    disabled={restoreMut.isPending}
                    onClick={async () => {
                      if (
                        await confirm(
                          t("p.collab.wiki.confirmRestore", {
                            version: r.version,
                          }),
                          { confirmLabel: t("p.collab.wiki.restore") },
                        )
                      ) {
                        restoreMut.mutate(r.version);
                      }
                    }}
                  >
                    <RotateCcw size={14} />
                  </IconButton>
                </Stack>
              ))}
            </Stack>
          )}
          {revDetail && previewRev !== null && (
            <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
              <Typography variant="caption" color="text.secondary" display="block" mb={1}>
                {t("p.collab.wiki.revisionPreview", { version: previewRev })}
              </Typography>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {revDetail.content || t("p.collab.wiki.noContent")}
              </ReactMarkdown>
            </Paper>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setHistoryFor(null)}>{t("common.close")}</Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle>
          {editing ? t("p.collab.wiki.editPage") : t("p.collab.wiki.newPage")}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("p.collab.field.title")}
              value={form.title}
              fullWidth
              autoFocus
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <TextField
              label={t("p.collab.field.project")}
              select
              fullWidth
              value={form.project}
              onChange={(e) => setForm({ ...form, project: e.target.value })}
            >
              <MenuItem value="">{t("p.collab.wiki.personal")}</MenuItem>
              {projects.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name}
                </MenuItem>
              ))}
            </TextField>
            <Suspense fallback={<CircularProgress size={24} />}>
              <MDEditor
                value={form.content}
                onChange={(v) => setForm({ ...form, content: v || "" })}
                height={340}
                preview="live"
                data-color-mode={themeMode === "dark" ? "dark" : "light"}
              />
            </Suspense>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => saveMut.mutate()}
            disabled={!form.title.trim() || saveMut.isPending}
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}