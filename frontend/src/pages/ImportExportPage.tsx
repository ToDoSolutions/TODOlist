import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Typography,
  Stack,
  Paper,
  Button,
  TextField,
  MenuItem,
  Stepper,
  Step,
  StepLabel,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Alert,
  Chip,
  Divider,
  Grid,
  LinearProgress,
} from "@mui/material";
import { Upload, Download, FileText, Copy, Link2, Trash2 } from "lucide-react";
import Papa from "papaparse";
import { saveAs } from "file-saver";
import PageHeader from "../components/ui/PageHeader";
import { env } from "../env";
import { tasksApi, projectsApi, tagsApi, userApi } from "../api/resources";
import { notify } from "../notify";
import { useProject } from "../auth/ProjectContext";
import {
  STATE_LABELS,
  PRIORITY_LABELS,
  type TaskInput,
  type TaskState,
  type TaskPriority,
} from "../types";
import { useTranslation } from "react-i18next";

type CsvRow = Record<string, string>;

// Mapeo campo CSV → campo Task. Nombres habituales de Jira/Trello/CSV genérico.
const FIELD_MAP: Record<string, string> = {
  title: "title",
  summary: "title",
  "issue summary": "title",
  nombre: "title",
  título: "title",
  card_name: "title",
  description: "description",
  desc: "description",
  descripción: "description",
  "issue description": "description",
  state: "state",
  status: "state",
  estado: "state",
  column: "state",
  priority: "priority",
  prioridad: "priority",
  severity: "priority",
  due: "due_date",
  "due date": "due_date",
  vencimiento: "due_date",
  due_date: "due_date",
};

const STEP_KEYS = [
  "p.shell.importExport.stepOrigin",
  "p.shell.importExport.stepMapping",
  "p.shell.importExport.stepPreview",
  "p.shell.importExport.stepResult",
];

// ===================== Importadores externos (Trello / Todoist) =====================
// Filas ya normalizadas a campos de Task; los labels de Trello se resuelven
// a tag ids en el momento de la importación (creando los que falten).

interface ExternalRow {
  title: string;
  description?: string;
  state?: TaskState;
  priority?: TaskPriority;
  due_date?: string | null;
  labelNames: string[];
}

// Sinónimos habituales de columnas de Trello → nuestro TaskState.
const TRELLO_LIST_STATE: Record<string, TaskState> = {
  backlog: "backlog",
  ideas: "backlog",
  "to do": "pending",
  todo: "pending",
  pending: "pending",
  pendiente: "pending",
  "por hacer": "pending",
  "in progress": "in_progress",
  doing: "in_progress",
  wip: "in_progress",
  "en progreso": "in_progress",
  blocked: "blocked",
  bloqueada: "blocked",
  bloqueado: "blocked",
  review: "review",
  "in review": "review",
  "code review": "review",
  "en revisión": "review",
  done: "completed",
  completed: "completed",
  finished: "completed",
  completada: "completed",
  completado: "completed",
  hecho: "completed",
  cancelled: "cancelled",
  canceled: "cancelled",
  cancelada: "cancelled",
  archived: "archived",
  archive: "archived",
  archivada: "archived",
};

function trelloListState(name: string): TaskState {
  const key = name.trim().toLowerCase();
  const direct = TRELLO_LIST_STATE[key];
  if (direct) return direct;
  const matched = Object.entries(STATE_LABELS).find(
    ([k, l]) => k === key || l.toLowerCase() === key,
  );
  return (matched?.[0] as TaskState | undefined) ?? "backlog";
}

interface TrelloCard {
  name?: string;
  desc?: string;
  due?: string | null;
  idList?: string;
  closed?: boolean;
  labels?: { name?: string }[];
}

function parseTrello(json: unknown): ExternalRow[] {
  const boards = Array.isArray(json) ? json : [json];
  const out: ExternalRow[] = [];
  for (const raw of boards) {
    if (!raw || typeof raw !== "object") continue;
    const board = raw as {
      lists?: { id?: string; name?: string; closed?: boolean }[];
      cards?: TrelloCard[];
    };
    const stateByList = new Map<string, TaskState>();
    for (const l of board.lists ?? []) {
      if (l.id) stateByList.set(l.id, trelloListState(l.name ?? ""));
    }
    for (const c of board.cards ?? []) {
      if (!c?.name || c.closed) continue;
      out.push({
        title: c.name,
        description: c.desc || undefined,
        state: (c.idList && stateByList.get(c.idList)) || "backlog",
        due_date: c.due ? c.due.slice(0, 10) : null,
        labelNames: (c.labels ?? [])
          .map((l) => l.name)
          .filter((n): n is string => !!n && !!n.trim()),
      });
    }
  }
  return out;
}

// Export CSV de Todoist: columnas TYPE,CONTENT,PRIORITY,INDENT,AUTHOR,
// RESPONSIBLE,DATE,DATE_LANG,TIMEZONE. Solo importamos filas TYPE=task.
function isTodoistCsv(headers: string[]): boolean {
  const h = new Set(headers.map((s) => s.trim().toUpperCase()));
  return h.has("TYPE") && h.has("CONTENT") && h.has("PRIORITY");
}

function parseTodoistDue(value: string | undefined): string | null {
  if (!value) return null;
  const iso = value.match(/\d{4}-\d{2}-\d{2}/);
  if (iso?.[0]) return iso[0];
  const d = new Date(value);
  return isNaN(d.getTime()) ? null : d.toISOString().slice(0, 10);
}

function parseTodoist(rows: CsvRow[]): ExternalRow[] {
  const out: ExternalRow[] = [];
  for (const r of rows) {
    if ((r.TYPE ?? "").trim().toLowerCase() !== "task") continue;
    const p = Number(r.PRIORITY);
    // Todoist: 1 = más urgente, 4 = mínima → mapeo directo a nuestro 0-3.
    const priority = isNaN(p)
      ? undefined
      : (Math.min(5, Math.max(0, p - 1)) as TaskPriority);
    const title = (r.CONTENT ?? "").trim();
    if (!title) continue;
    out.push({
      title,
      description: r.DESCRIPTION?.trim() || undefined,
      priority,
      due_date: parseTodoistDue(r.DATE),
      labelNames: [],
    });
  }
  return out;
}

export default function ImportExportPage() {
  const { t } = useTranslation();
  const { project: ctxProject } = useProject();
  const qc = useQueryClient();
  const [step, setStep] = useState(0);
  const [rows, setRows] = useState<CsvRow[]>([]);
  const [headers, setHeaders] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [targetProject, setTargetProject] = useState<number | "">(ctxProject?.id ?? "");
  const [result, setResult] = useState<{ created: number; errors: number } | null>(null);
  const [icalUrl, setIcalUrl] = useState<string | null>(null);
  // Filas de importadores externos (Trello JSON / Todoist CSV): se saltan el
  // paso de mapeo y van directas a la vista previa.
  const [extRows, setExtRows] = useState<ExternalRow[] | null>(null);
  const [extSource, setExtSource] = useState<string | null>(null);
  const [progress, setProgress] = useState<{
    done: number;
    errors: number;
    total: number;
  } | null>(null);

  const icalMut = useMutation({
    mutationFn: userApi.calendarToken,
    onSuccess: (data) => {
      // feed_url es un path relativo (/api/tasks/...); anteponer el origen
      const base = env.VITE_API_URL.replace(/\/api\/?$/, "");
      setIcalUrl(`${base}${data.feed_url}`);
    },
    onError: () => notify.error(t("p.shell.importExport.errorGenerateUrl")),
  });
  const revokeMut = useMutation({
    mutationFn: userApi.calendarTokenRevoke,
    onSuccess: () => {
      setIcalUrl(null);
      notify.success(t("p.shell.importExport.urlRevoked"));
    },
    onError: () => notify.error(t("p.shell.importExport.errorRevoke")),
  });

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData) ? projectsData : [];

  const { data: tasksData } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => tasksApi.list({}),
  });
  const allTasks = Array.isArray(tasksData) ? tasksData : [];

  const loadExtRows = (parsed: ExternalRow[], source: string) => {
    if (!parsed.length) {
      notify.error(t("p.public.import.emptyFile"));
      return;
    }
    setExtRows(parsed);
    setExtSource(source);
    setStep(2);
  };

  const onFile = (file: File) => {
    setExtRows(null);
    setExtSource(null);
    setResult(null);
    setProgress(null);
    if (file.name.toLowerCase().endsWith(".json")) {
      const reader = new FileReader();
      reader.onload = () => {
        try {
          loadExtRows(parseTrello(JSON.parse(String(reader.result))), "Trello");
        } catch {
          notify.error(t("p.public.import.parseError"));
        }
      };
      reader.onerror = () => notify.error(t("p.public.import.parseError"));
      reader.readAsText(file);
      return;
    }
    Papa.parse<CsvRow>(file, {
      header: true,
      skipEmptyLines: true,
      complete: (res) => {
        const hdrs = res.meta.fields ?? [];
        if (isTodoistCsv(hdrs)) {
          loadExtRows(parseTodoist(res.data), "Todoist");
          return;
        }
        setHeaders(hdrs);
        setRows(res.data);
        const auto: Record<string, string> = {};
        for (const h of hdrs) {
          const mapped = FIELD_MAP[h.toLowerCase().trim()];
          if (mapped) auto[h] = mapped;
        }
        setMapping(auto);
        setStep(1);
      },
      error: () => notify.error(t("p.shell.importExport.errorReadCsv")),
    });
  };

  const mappedRows = useMemo(
    () =>
      rows.map((r) => {
        const out: Record<string, unknown> = {};
        for (const [csvCol, taskField] of Object.entries(mapping)) {
          if (!taskField || r[csvCol] == null || r[csvCol] === "") continue;
          const v = r[csvCol];
          if (taskField === "priority") {
            const num = Number(v);
            out.priority = isNaN(num)
              ? Number(
                  Object.entries(PRIORITY_LABELS).find(
                    ([, l]) => l.toLowerCase() === v.toLowerCase(),
                  )?.[0] ?? 3,
                )
              : Math.min(5, Math.max(0, num));
          } else if (taskField === "state") {
            out.state =
              Object.entries(STATE_LABELS).find(
                ([k, l]) => k === v || l.toLowerCase() === v.toLowerCase(),
              )?.[0] ?? "backlog";
          } else {
            out[taskField] = v;
          }
        }
        return out;
      }),
    [rows, mapping],
  );

  // Resuelve nombres de label (Trello) a ids de Tag, creando los que falten.
  const resolveTagIds = async (names: string[]): Promise<Map<string, number>> => {
    const map = new Map<string, number>();
    const wanted = new Set(names.map((n) => n.trim().toLowerCase()).filter(Boolean));
    if (!wanted.size) return map;
    try {
      for (const tg of await tagsApi.list()) map.set(tg.name.toLowerCase(), tg.id);
      for (const key of wanted) {
        if (map.has(key)) continue;
        try {
          const created = await tagsApi.create({ name: key });
          if (created?.id != null) map.set(key, created.id);
        } catch {
          // Si el tag no se puede crear, la tarea entra sin él.
        }
      }
    } catch {
      // Sin acceso a tags: se importa sin etiquetas.
    }
    return map;
  };

  const buildTaskInputs = async (): Promise<TaskInput[]> => {
    const project = targetProject === "" ? null : Number(targetProject);
    if (extRows) {
      const tagIds = await resolveTagIds(extRows.flatMap((r) => r.labelNames));
      return extRows.map((r) => ({
        title: r.title,
        description: r.description,
        state: r.state,
        priority: r.priority,
        due_date: r.due_date ?? null,
        project,
        tags: r.labelNames
          .map((n) => tagIds.get(n.trim().toLowerCase()))
          .filter((id): id is number => id != null),
      }));
    }
    return mappedRows
      .filter((row) => row.title)
      .map((row) => ({ ...row, project }) as TaskInput);
  };

  const importMut = useMutation({
    mutationFn: async () => {
      let created = 0;
      let errors = 0;
      const inputs = await buildTaskInputs();
      setProgress({ done: 0, errors: 0, total: inputs.length });
      for (const input of inputs) {
        try {
          await tasksApi.create(input);
          created++;
        } catch {
          errors++;
        }
        setProgress({ done: created + errors, errors, total: inputs.length });
      }
      return { created, errors };
    },
    onSuccess: (r) => {
      setResult(r);
      setStep(3);
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["tags"] });
      notify.success(
        `${t("p.shell.importExport.importedCount", { created: r.created })}${
          r.errors ? t("p.shell.importExport.importedErrors", { errors: r.errors }) : ""
        }`,
      );
    },
  });

  const exportCsv = () => {
    const csv = Papa.unparse(
      allTasks.map((t) => ({
        id: t.id,
        title: t.title,
        state: t.state,
        priority: t.priority,
        project: t.project ?? "",
        sprint: t.sprint_name ?? "",
        assignee: t.assignee_email ?? "",
        due: t.due_date ?? "",
      })),
    );
    saveAs(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
      `tareas-${new Date().toISOString().slice(0, 10)}.csv`,
    );
    notify.success(t("p.shell.importExport.exportedCount", { count: allTasks.length }));
  };

  // Filas a previsualizar: importador externo si hay, si no el CSV mapeado.
  const previewRows = (extRows ?? mappedRows) as {
    title?: unknown;
    state?: unknown;
    priority?: unknown;
    due_date?: unknown;
  }[];
  const importCount = extRows ? extRows.length : mappedRows.filter((r) => r.title).length;

  return (
    <Box>
      <PageHeader
        title={t("p.shell.importExport")}
        description={t("p.shell.importExport.pageDesc")}
        breadcrumbs={[
          { label: t("p.shell.administration"), to: "/app/admin" },
          { label: t("p.shell.importExport") },
        ]}
      />

      <Stepper activeStep={step} sx={{ mb: 4 }}>
        {STEP_KEYS.map((s) => (
          <Step key={s}>
            <StepLabel>{t(s)}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {step === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper variant="outlined" sx={{ p: 3, textAlign: "center" }}>
              <Upload size={32} style={{ marginBottom: 8 }} />
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                {t("p.public.import.fileTitle")}
              </Typography>
              <Typography variant="body2" color="text.secondary" mb={2}>
                {t("p.public.import.fileDesc")}
              </Typography>
              <Button
                variant="contained"
                component="label"
                startIcon={<FileText size={16} />}
              >
                {t("p.public.import.selectFile")}
                <input
                  type="file"
                  hidden
                  accept=".csv,.json"
                  onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
                />
              </Button>
            </Paper>
          </Grid>
          <Grid item xs={12} md={6}>
            <Paper variant="outlined" sx={{ p: 3, textAlign: "center" }}>
              <Download size={32} style={{ marginBottom: 8 }} />
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                {t("p.shell.importExport.exportTitle")}
              </Typography>
              <Typography variant="body2" color="text.secondary" mb={2}>
                {t("p.shell.importExport.exportDesc")}
              </Typography>
              <Stack direction="row" spacing={1} justifyContent="center">
                <Button variant="outlined" onClick={exportCsv}>
                  CSV
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => window.open("/api/tasks/calendar.ics/", "_blank")}
                >
                  iCal (.ics)
                </Button>
              </Stack>

              {/* Suscripción iCal: token opaco para clientes de calendario
                  (Google/Outlook/Apple no envían JWT ni cookies) */}
              <Divider sx={{ my: 2 }} />
              <Typography variant="body2" color="text.secondary" mb={1}>
                {t("p.shell.importExport.icalDesc")}
              </Typography>
              {!icalUrl ? (
                <Button
                  variant="text"
                  size="small"
                  startIcon={<Link2 size={15} />}
                  onClick={() => icalMut.mutate()}
                  disabled={icalMut.isPending}
                >
                  {t("p.shell.importExport.generateUrl")}
                </Button>
              ) : (
                <Stack direction="row" spacing={1} alignItems="center">
                  <TextField
                    size="small"
                    fullWidth
                    value={icalUrl}
                    InputProps={{ readOnly: true }}
                    onFocus={(e) => e.target.select()}
                  />
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<Copy size={15} />}
                    onClick={() => {
                      void navigator.clipboard.writeText(icalUrl);
                      notify.success(t("p.shell.importExport.urlCopied"));
                    }}
                  >
                    {t("p.shell.importExport.copy")}
                  </Button>
                  <Button
                    size="small"
                    color="error"
                    variant="outlined"
                    startIcon={<Trash2 size={15} />}
                    onClick={() => revokeMut.mutate()}
                    disabled={revokeMut.isPending}
                  >
                    {t("p.shell.importExport.revoke")}
                  </Button>
                </Stack>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}

      {step === 1 && (
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Typography variant="subtitle1" fontWeight={700} mb={2}>
            {t("p.shell.importExport.mappingTitle", { count: rows.length })}
          </Typography>
          <Stack spacing={1.5}>
            {headers.map((h) => (
              <Stack key={h} direction="row" spacing={2} alignItems="center">
                <Typography variant="body2" sx={{ minWidth: 200 }} fontWeight={600}>
                  {h}
                </Typography>
                <Typography color="text.secondary">→</Typography>
                <TextField
                  select
                  size="small"
                  value={mapping[h] ?? ""}
                  onChange={(e) => setMapping({ ...mapping, [h]: e.target.value })}
                  sx={{ minWidth: 180 }}
                >
                  <MenuItem value="">{t("p.shell.importExport.ignoreField")}</MenuItem>
                  {["title", "description", "state", "priority", "due_date"].map((f) => (
                    <MenuItem key={f} value={f}>
                      {f}
                    </MenuItem>
                  ))}
                </TextField>
              </Stack>
            ))}
          </Stack>
          <Divider sx={{ my: 2 }} />
          <TextField
            select
            size="small"
            label={t("p.shell.importExport.targetProject")}
            value={targetProject}
            onChange={(e) =>
              setTargetProject(e.target.value === "" ? "" : Number(e.target.value))
            }
            sx={{ minWidth: 240 }}
          >
            <MenuItem value="">{t("nav.inbox")}</MenuItem>
            {projects.map((p) => (
              <MenuItem key={p.id} value={p.id}>
                {p.name}
              </MenuItem>
            ))}
          </TextField>
          <Stack direction="row" spacing={1} mt={3}>
            <Button onClick={() => setStep(0)}>{t("p.shell.importExport.back")}</Button>
            <Button
              variant="contained"
              onClick={() => setStep(2)}
              disabled={!Object.values(mapping).includes("title")}
            >
              {t("p.shell.importExport.stepPreview")}
            </Button>
          </Stack>
          {!Object.values(mapping).includes("title") && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              {t("p.shell.importExport.mustMapTitle")}
            </Alert>
          )}
        </Paper>
      )}

      {step === 2 && (
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack direction="row" alignItems="center" spacing={1} mb={2}>
            <Typography variant="subtitle1" fontWeight={700}>
              {t("p.public.import.previewRows", {
                count: Math.min(20, previewRows.length),
                total: previewRows.length,
              })}
            </Typography>
            {extSource && (
              <Chip
                size="small"
                variant="outlined"
                label={t("p.public.import.source", { source: extSource })}
              />
            )}
          </Stack>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t("p.board.colTitle")}</TableCell>
                <TableCell>{t("p.board.colState")}</TableCell>
                <TableCell>{t("p.board.colPriority")}</TableCell>
                <TableCell>{t("p.board.colDue")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {previewRows.slice(0, 20).map((r, i) => (
                <TableRow key={i}>
                  <TableCell>{String(r.title ?? "—")}</TableCell>
                  <TableCell>
                    {STATE_LABELS[r.state as keyof typeof STATE_LABELS] ??
                      String(r.state ?? "backlog")}
                  </TableCell>
                  <TableCell>
                    {PRIORITY_LABELS[r.priority as keyof typeof PRIORITY_LABELS] ??
                      String(r.priority ?? 3)}
                  </TableCell>
                  <TableCell>{String(r.due_date ?? "—")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {extRows && (
            <TextField
              select
              size="small"
              label={t("p.shell.importExport.targetProject")}
              value={targetProject}
              onChange={(e) =>
                setTargetProject(e.target.value === "" ? "" : Number(e.target.value))
              }
              sx={{ minWidth: 240, mt: 2 }}
            >
              <MenuItem value="">{t("nav.inbox")}</MenuItem>
              {projects.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name}
                </MenuItem>
              ))}
            </TextField>
          )}
          {importMut.isPending && progress && (
            <Box mt={2}>
              <LinearProgress
                variant="determinate"
                value={progress.total ? (progress.done / progress.total) * 100 : 0}
              />
              <Typography variant="caption" color="text.secondary">
                {t("p.public.import.progress", {
                  done: progress.done,
                  total: progress.total,
                  errors: progress.errors,
                })}
              </Typography>
            </Box>
          )}
          <Stack direction="row" spacing={1} mt={3}>
            <Button
              onClick={() => setStep(extRows ? 0 : 1)}
              disabled={importMut.isPending}
            >
              {t("p.shell.importExport.back")}
            </Button>
            <Button
              variant="contained"
              onClick={() => importMut.mutate()}
              disabled={importMut.isPending}
            >
              {t("p.public.import.importN", { count: importCount })}
            </Button>
          </Stack>
        </Paper>
      )}

      {step === 3 && result && (
        <Paper variant="outlined" sx={{ p: 3, textAlign: "center" }}>
          <Typography variant="h6" fontWeight={700} mb={1}>
            {result.errors === 0
              ? t("p.public.import.done")
              : t("p.public.import.partial")}
          </Typography>
          <Stack direction="row" spacing={2} justifyContent="center" mb={2}>
            <Chip
              label={t("p.public.import.createdChip", { count: result.created })}
              color="success"
              variant="outlined"
            />
            {result.errors > 0 && (
              <Chip
                label={t("p.public.import.errorsChip", { count: result.errors })}
                color="error"
                variant="outlined"
              />
            )}
          </Stack>
          <Button
            variant="outlined"
            onClick={() => {
              setStep(0);
              setRows([]);
              setExtRows(null);
              setExtSource(null);
              setProgress(null);
              setResult(null);
            }}
          >
            {t("p.public.import.newImport")}
          </Button>
        </Paper>
      )}
    </Box>
  );
}
