import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CardGridSkeleton } from "../components/ui/skeletons";
import {
  Box,
  Typography,
  Stack,
  Paper,
  Button,
  TextField,
  MenuItem,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  CircularProgress,
  Tooltip,
} from "@mui/material";
import {
  Plus,
  Trash2,
  ArrowLeft,
  RefreshCw,
  StickyNote,
  Link2,
  X,
  Presentation,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { formatDateTime } from "../lib/dates";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState, ErrorState } from "../components/ui/states";
import { projectsApi } from "../api/resources";
import {
  whiteboardsApi,
  type WhiteboardContent,
  type WhiteboardNode,
} from "../api/featExtras";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import "../i18n";

const CANVAS_W = 2000;
const CANVAS_H = 1400;
const NOTE_W = 220;
const NOTE_H = 140;
const SAVE_DEBOUNCE_MS = 800;

const emptyContent = (): WhiteboardContent => ({ nodes: [], edges: [] });

const normalizeContent = (c: WhiteboardContent | null | undefined) => ({
  nodes: Array.isArray(c?.nodes) ? c.nodes : [],
  edges: Array.isArray(c?.edges) ? c.edges : [],
});

const newNodeId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `n-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

export default function WhiteboardsPage() {
  const { id } = useParams();
  return id ? <WhiteboardDetail id={Number(id)} /> : <WhiteboardList />;
}

/* ------------------------------- Lista ---------------------------------- */

function WhiteboardList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [dialog, setDialog] = useState(false);
  const [form, setForm] = useState({ project: "", name: "" });

  const { data: whiteboards = [] } = useQuery({
    queryKey: ["whiteboards"],
    queryFn: whiteboardsApi.list,
  });
  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData) ? projectsData : [];
  const projectName = (id: number) => projects.find((p) => p.id === id)?.name || `#${id}`;

  const createMut = useMutation({
    mutationFn: () =>
      whiteboardsApi.create({
        project: Number(form.project),
        name: form.name.trim(),
      }),
    onSuccess: (wb) => {
      qc.invalidateQueries({ queryKey: ["whiteboards"] });
      setDialog(false);
      setForm({ project: "", name: "" });
      notify.success(t("p.extras.wb.created"));
      navigate(`/app/whiteboards/${wb.id}`);
    },
    onError: () => notify.error(t("p.extras.wb.createError")),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => whiteboardsApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["whiteboards"] });
      notify.success(t("p.extras.wb.deleted"));
    },
    onError: () => notify.error(t("p.extras.wb.deleteError")),
  });

  return (
    <Box>
      <PageHeader
        title={t("p.extras.wb.title")}
        description={t("p.extras.wb.desc")}
        breadcrumbs={[
          { label: t("nav.projects") },
          { label: t("p.extras.wb.title") },
        ]}
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={15} />}
            onClick={() => setDialog(true)}
          >
            {t("p.extras.wb.new")}
          </Button>
        }
      />

      {whiteboards.length === 0 ? (
        <EmptyState
          title={t("p.extras.wb.emptyTitle")}
          description={t("p.extras.wb.emptyDesc")}
          icon={<Presentation size={48} strokeWidth={1.2} />}
          action={
            <Button
              variant="outlined"
              startIcon={<Plus size={15} />}
              onClick={() => setDialog(true)}
            >
              {t("p.extras.wb.new")}
            </Button>
          }
        />
      ) : (
        <Stack spacing={1}>
          {whiteboards.map((wb) => (
            <Paper
              key={wb.id}
              variant="outlined"
              sx={{
                p: 1.5,
                cursor: "pointer",
                "&:hover": { borderColor: "primary.main" },
              }}
              onClick={() => navigate(`/app/whiteboards/${wb.id}`)}
            >
              <Stack direction="row" alignItems="center" spacing={1.5}>
                <Presentation size={18} />
                <Box flex={1} minWidth={0}>
                  <Typography variant="body2" fontWeight={600} noWrap>
                    {wb.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {t("p.extras.wb.updated", {
                      date: formatDateTime(wb.updated_at),
                    })}
                  </Typography>
                </Box>
                <Chip size="small" variant="outlined" label={projectName(wb.project)} />
                <IconButton
                  size="small"
                  color="error"
                  aria-label={t("p.extras.wb.deleteAria")}
                  onClick={async (e) => {
                    e.stopPropagation();
                    if (
          await confirm(t("p.extras.wb.confirmDelete"), {
            confirmLabel: t("common.delete"),
          })
        )
                      deleteMut.mutate(wb.id);
                  }}
                >
                  <Trash2 size={16} />
                </IconButton>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      {/* Nueva pizarra */}
      <Dialog open={dialog} onClose={() => setDialog(false)} fullWidth maxWidth="xs">
        <DialogTitle>{t("p.extras.wb.new")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField
              select
              label={t("p.extras.wb.project")}
              fullWidth
              value={form.project}
              onChange={(e) => setForm({ ...form, project: e.target.value })}
            >
              {projects.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label={t("p.extras.wb.name")}
              fullWidth
              autoFocus
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={!form.project || !form.name.trim() || createMut.isPending}
            onClick={() => createMut.mutate()}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

/* ------------------------------- Detalle -------------------------------- */

function WhiteboardDetail({ id }: { id: number }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const {
    data: wb,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["whiteboard", id],
    queryFn: () => whiteboardsApi.get(id),
    retry: false,
  });

  // Contenido local editable; el servidor manda la copia canónica al cargar.
  const [content, setContent] = useState<WhiteboardContent>(emptyContent);
  const contentRef = useRef(content);
  const loadedIdRef = useRef<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [connectMode, setConnectMode] = useState(false);
  const [pendingFrom, setPendingFrom] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const canvasRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{
    id: string;
    grabX: number;
    grabY: number;
    w: number;
    h: number;
  } | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingSave = useRef<WhiteboardContent | null>(null);

  useEffect(() => {
    if (wb && wb.id !== loadedIdRef.current) {
      loadedIdRef.current = wb.id;
      const c = normalizeContent(wb.content);
      contentRef.current = c;
      setContent(c);
    }
  }, [wb]);

  const saveMut = useMutation({
    mutationFn: (c: WhiteboardContent) => whiteboardsApi.update(id, { content: c }),
    onSuccess: () => {
      pendingSave.current = null;
      setDirty(false);
      qc.invalidateQueries({ queryKey: ["whiteboards"] });
    },
    onError: () => notify.error(t("p.extras.wb.saveError")),
  });

  const scheduleSave = (c: WhiteboardContent) => {
    pendingSave.current = c;
    setDirty(true);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      if (pendingSave.current) saveMut.mutate(pendingSave.current);
    }, SAVE_DEBOUNCE_MS);
  };

  // Al desmontar, flush del último estado pendiente para no perder el
  // drag final si el usuario navega dentro del debounce.
  useEffect(() => {
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
      const pending = pendingSave.current;
      if (pending) {
        pendingSave.current = null;
        void whiteboardsApi.update(id, { content: pending }).catch(() => {});
      }
    };
  }, [id]);

  const updateContent = (fn: (c: WhiteboardContent) => WhiteboardContent) => {
    const next = fn(contentRef.current);
    contentRef.current = next;
    setContent(next);
    scheduleSave(next);
  };

  const updateLocal = (fn: (c: WhiteboardContent) => WhiteboardContent) => {
    const next = fn(contentRef.current);
    contentRef.current = next;
    setContent(next);
  };

  /* Notas */
  const addNote = () => {
    const idx = contentRef.current.nodes.length;
    const node: WhiteboardNode = {
      id: newNodeId(),
      x: 40 + ((idx * 60) % (CANVAS_W - NOTE_W - 80)),
      y: 40 + ((idx * 60) % (CANVAS_H - NOTE_H - 80)),
      text: "",
      color: "#fff9c4",
      w: NOTE_W,
      h: NOTE_H,
    };
    updateContent((c) => ({ ...c, nodes: [...c.nodes, node] }));
    setEditingId(node.id);
    setDraft("");
  };

  const removeNode = (nodeId: string) => {
    updateContent((c) => ({
      nodes: c.nodes.filter((n) => n.id !== nodeId),
      edges: c.edges.filter((e) => e.from !== nodeId && e.to !== nodeId),
    }));
    if (pendingFrom === nodeId) setPendingFrom(null);
    if (editingId === nodeId) setEditingId(null);
  };

  const commitEdit = () => {
    if (!editingId) return;
    const text = draft;
    updateContent((c) => ({
      ...c,
      nodes: c.nodes.map((n) => (n.id === editingId ? { ...n, text } : n)),
    }));
    setEditingId(null);
  };

  /* Conexiones */
  const toggleConnect = () => {
    setConnectMode((m) => !m);
    setPendingFrom(null);
  };

  const onConnectPick = (nodeId: string) => {
    if (!pendingFrom) {
      setPendingFrom(nodeId);
      return;
    }
    if (pendingFrom !== nodeId) {
      const from = pendingFrom;
      updateContent((c) => {
        const exists = c.edges.some(
          (e) =>
            (e.from === from && e.to === nodeId) || (e.from === nodeId && e.to === from),
        );
        return exists ? c : { ...c, edges: [...c.edges, { from, to: nodeId }] };
      });
    }
    setPendingFrom(null);
  };

  const removeEdge = (idx: number) =>
    updateContent((c) => ({ ...c, edges: c.edges.filter((_, i) => i !== idx) }));

  /* Drag con pointer events */
  const onNodePointerDown = (e: React.PointerEvent, node: WhiteboardNode) => {
    if (connectMode) {
      e.preventDefault();
      onConnectPick(node.id);
      return;
    }
    if (editingId === node.id) return;
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    const rect = el.getBoundingClientRect();
    dragRef.current = {
      id: node.id,
      grabX: e.clientX - rect.left,
      grabY: e.clientY - rect.top,
      w: node.w,
      h: node.h,
    };
  };

  const onNodePointerMove = (e: React.PointerEvent) => {
    const drag = dragRef.current;
    const canvas = canvasRef.current;
    if (!drag || !canvas) return;
    const crect = canvas.getBoundingClientRect();
    const x = Math.round(
      Math.min(Math.max(e.clientX - crect.left - drag.grabX, 0), CANVAS_W - drag.w),
    );
    const y = Math.round(
      Math.min(Math.max(e.clientY - crect.top - drag.grabY, 0), CANVAS_H - drag.h),
    );
    updateLocal((c) => ({
      ...c,
      nodes: c.nodes.map((n) => (n.id === drag.id ? { ...n, x, y } : n)),
    }));
  };

  const onNodePointerUp = () => {
    if (!dragRef.current) return;
    dragRef.current = null;
    scheduleSave(contentRef.current);
  };

  if (isLoading)
    return (
      <CardGridSkeleton />
    );
  if (isError || !wb)
    return (
      <ErrorState
        title={isError ? t("p.extras.wb.loadError") : t("p.extras.wb.notFound")}
        onRetry={() => refetch()}
        action={
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              startIcon={<RefreshCw size={15} />}
              onClick={() => refetch()}
            >
              {t("p.extras.wb.retry")}
            </Button>
            <Button
              startIcon={<ArrowLeft size={15} />}
              onClick={() => navigate("/app/whiteboards")}
            >
              {t("p.extras.wb.back")}
            </Button>
          </Stack>
        }
      />
    );

  const nodeById = (nodeId: string) => content.nodes.find((n) => n.id === nodeId);

  return (
    <Box>
      <PageHeader
        title={wb.name}
        breadcrumbs={[
          { label: t("p.extras.wb.title"), to: "/app/whiteboards" },
          { label: wb.name },
        ]}
        actions={
          <>
            {connectMode && (
              <Chip
                size="small"
                color="primary"
                variant="outlined"
                label={t("p.extras.wb.connectHint")}
              />
            )}
            <Chip
              size="small"
              variant="outlined"
              label={
                dirty || saveMut.isPending
                  ? t("p.extras.wb.saving")
                  : t("p.extras.wb.saved")
              }
              color={dirty || saveMut.isPending ? "warning" : "success"}
            />
            <Button
              variant={connectMode ? "contained" : "outlined"}
              size="small"
              startIcon={<Link2 size={15} />}
              onClick={toggleConnect}
            >
              {connectMode ? t("p.extras.wb.connectActive") : t("p.extras.wb.connect")}
            </Button>
            <Button
              variant="contained"
              size="small"
              startIcon={<StickyNote size={15} />}
              onClick={addNote}
            >
              {t("p.extras.wb.addNote")}
            </Button>
          </>
        }
      />

      {/* Lienzo scrollable */}
      <Paper
        variant="outlined"
        sx={{
          overflow: "auto",
          maxHeight: "calc(100vh - 220px)",
          bgcolor: "action.hover",
        }}
      >
        <Box
          ref={canvasRef}
          sx={{
            position: "relative",
            width: CANVAS_W,
            height: CANVAS_H,
            backgroundImage:
              "radial-gradient(circle, rgba(0,0,0,0.08) 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
        >
          {/* Aristas bajo las notas */}
          <svg
            width={CANVAS_W}
            height={CANVAS_H}
            style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none" }}
          >
            {content.edges.map((edge, i) => {
              const a = nodeById(edge.from);
              const b = nodeById(edge.to);
              if (!a || !b) return null;
              const x1 = a.x + a.w / 2;
              const y1 = a.y + a.h / 2;
              const x2 = b.x + b.w / 2;
              const y2 = b.y + b.h / 2;
              return (
                <g key={`${edge.from}-${edge.to}-${i}`}>
                  {/* línea invisible ancha: objetivo de click cómodo */}
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke="transparent"
                    strokeWidth={14}
                    style={{
                      pointerEvents: connectMode ? "stroke" : "none",
                      cursor: connectMode ? "pointer" : "default",
                    }}
                    onClick={() => connectMode && removeEdge(i)}
                  />
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke="#90a4ae"
                    strokeWidth={connectMode ? 3 : 2}
                    strokeDasharray={connectMode ? "6 4" : undefined}
                  />
                </g>
              );
            })}
          </svg>

          {content.nodes.map((node) => (
            <Paper
              key={node.id}
              elevation={3}
              onPointerDown={(e) => onNodePointerDown(e, node)}
              onPointerMove={onNodePointerMove}
              onPointerUp={onNodePointerUp}
              onDoubleClick={() => {
                if (connectMode) return;
                setEditingId(node.id);
                setDraft(node.text);
              }}
              sx={{
                position: "absolute",
                left: node.x,
                top: node.y,
                width: node.w,
                minHeight: node.h,
                bgcolor: node.color || "#fff9c4",
                p: 1,
                userSelect: "none",
                touchAction: "none",
                cursor: connectMode ? "crosshair" : "grab",
                outline: pendingFrom === node.id ? "3px solid" : "none",
                outlineColor: "primary.main",
                "&:active": { cursor: connectMode ? "crosshair" : "grabbing" },
              }}
            >
              <Tooltip title={t("p.extras.wb.noteDeleteAria")}>
                <IconButton
                  size="small"
                  aria-label={t("p.extras.wb.noteDeleteAria")}
                  onPointerDown={(e) => e.stopPropagation()}
                  onClick={(e) => {
                    e.stopPropagation();
                    removeNode(node.id);
                  }}
                  sx={{ position: "absolute", top: 2, right: 2 }}
                >
                  <X size={12} />
                </IconButton>
              </Tooltip>
              {editingId === node.id ? (
                <TextField
                  multiline
                  autoFocus
                  fullWidth
                  variant="standard"
                  value={draft}
                  placeholder={t("p.extras.wb.notePlaceholder")}
                  onChange={(e) => setDraft(e.target.value)}
                  onBlur={commitEdit}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") commitEdit();
                  }}
                  onClick={(e) => e.stopPropagation()}
                  onPointerDown={(e) => e.stopPropagation()}
                  InputProps={{ sx: { fontSize: 13 } }}
                />
              ) : (
                <Typography
                  variant="body2"
                  sx={{
                    whiteSpace: "pre-wrap",
                    pr: 2,
                    fontSize: 13,
                    color: node.text ? "text.primary" : "text.disabled",
                  }}
                >
                  {node.text || t("p.extras.wb.notePlaceholder")}
                </Typography>
              )}
            </Paper>
          ))}
        </Box>
      </Paper>
    </Box>
  );
}