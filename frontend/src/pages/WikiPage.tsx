import { lazy, Suspense, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

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
  Alert,
  MenuItem,
} from "@mui/material";
import { Plus, FileText, Pencil, Trash2 } from "lucide-react";
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
  const [form, setForm] = useState({
    title: "",
    content: "",
    project: "" as string | number,
  });

  const {
    data: pages = [],
    isLoading,
    isError,
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
        <IconButton size="small" onClick={() => openEdit(p)}>
          <Pencil size={14} />
        </IconButton>
        <IconButton
          size="small"
          color="error"
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
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={800}>
            {t("p.collab.wiki.title")}
          </Typography>
          <Typography variant="body2" color="text.secondary" mt={0.5}>
            {t("p.collab.wiki.subtitle")}
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<Plus size={18} />} onClick={openNew}>
          {t("p.collab.wiki.newPage")}
        </Button>
      </Stack>

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {t("p.collab.wiki.loadError")}
        </Alert>
      )}
      {isLoading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
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
