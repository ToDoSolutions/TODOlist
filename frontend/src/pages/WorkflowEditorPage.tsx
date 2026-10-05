import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Typography,
  Stack,
  Paper,
  Chip,
  Button,
  IconButton,
  TextField,
  MenuItem,
  Alert,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Tooltip,
} from "@mui/material";
import { ArrowRight, Plus, Trash2, AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/states";
import { workflowApi, projectsApi } from "../api/resources";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import { useProject } from "../auth/ProjectContext";
import { STATE_LABELS, type TaskState } from "../types";

const STATES = Object.keys(STATE_LABELS) as TaskState[];

/**
 * Editor de workflows: transiciones permitidas por proyecto.
 * Vista gráfica de nodos + tabla accesible + detección de estados sin salida.
 */
export default function WorkflowEditorPage() {
  const { t } = useTranslation();
  const { project: ctxProject } = useProject();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [projectId, setProjectId] = useState<number | "">(ctxProject?.id ?? "");
  const [from, setFrom] = useState<TaskState | "">("");
  const [to, setTo] = useState<TaskState | "">("");

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData) ? projectsData : [];

  // Preselecciona el primer proyecto — evita la pantalla "Selecciona
  // un proyecto" que obliga a un clic extra siempre.
  useEffect(() => {
    if (projectId === "" && projects.length > 0) {
      const first = projects[0] as { id?: number };
      if (first?.id != null) setProjectId(first.id);
    }
  }, [projects, projectId]);

  const { data: transitions } = useQuery({
    queryKey: ["workflow-transitions", projectId],
    queryFn: () => workflowApi.list(projectId ? Number(projectId) : undefined),
    enabled: projectId !== "",
  });
  const edges = Array.isArray(transitions) ? transitions : [];

  const createMut = useMutation({
    mutationFn: () =>
      workflowApi.create({ project: Number(projectId), from_state: from, to_state: to }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workflow-transitions", projectId] });
      setFrom("");
      setTo("");
      notify.success(t("p.ops.workflow.added"));
    },
    onError: (e: unknown) => {
      const msg = (
        e as { response?: { data?: { detail?: string; non_field_errors?: string[] } } }
      )?.response?.data;
      notify.error(
        msg?.non_field_errors?.[0] ?? msg?.detail ?? t("p.ops.workflow.createError"),
      );
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => workflowApi.remove(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["workflow-transitions", projectId] }),
  });

  // Estados sin transición de salida: puntos muertos del flujo
  const statesWithOut = new Set(edges.map((e) => e.from_state));
  const deadEnds = STATES.filter(
    (s) => !statesWithOut.has(s) && s !== "archived" && edges.length > 0,
  );

  return (
    <Box>
      <PageHeader
        title={t("p.ops.workflow.title")}
        description={t("p.ops.workflow.description")}
        breadcrumbs={[
          { label: t("p.ops.workflow.breadcrumbSettings") },
          { label: t("p.ops.workflow.title") },
        ]}
      />

      <TextField
        select
        size="small"
        label={t("p.ops.project")}
        value={projectId}
        onChange={(e) =>
          setProjectId(e.target.value === "" ? "" : Number(e.target.value))
        }
        sx={{ minWidth: 240, mb: 3 }}
      >
        <MenuItem value="">{t("p.ops.selectProject")}</MenuItem>
        {projects.map((p) => (
          <MenuItem key={p.id} value={p.id}>
            {p.name}
          </MenuItem>
        ))}
      </TextField>

      {projectId === "" ? (
        <EmptyState
          title={t("p.ops.selectProject")}
          description={t("p.ops.workflow.emptyDesc")}
        />
      ) : (
        <>
          {/* Vista gráfica: nodos conectados por flechas */}
          <Paper variant="outlined" sx={{ p: 2.5, mb: 3, overflowX: "auto" }}>
            <Typography variant="subtitle2" fontWeight={700} mb={2}>
              {t("p.ops.workflow.mapTitle")}
            </Typography>
            {edges.length === 0 ? (
              <Alert severity="info">{t("p.ops.workflow.noTransitions")}</Alert>
            ) : (
              <Stack spacing={1}>
                {STATES.map((s) => {
                  const outs = edges.filter((e) => e.from_state === s);
                  if (outs.length === 0 && !edges.some((e) => e.to_state === s))
                    return null;
                  return (
                    <Stack
                      key={s}
                      direction="row"
                      spacing={1}
                      alignItems="center"
                      flexWrap="wrap"
                      useFlexGap
                    >
                      <Chip
                        label={STATE_LABELS[s]}
                        color="primary"
                        variant="outlined"
                        sx={{ minWidth: 110 }}
                      />
                      {outs.length === 0 ? (
                        <Typography variant="caption" color="text.secondary">
                          {t("p.ops.workflow.finalDest")}
                        </Typography>
                      ) : (
                        outs.map((e) => (
                          <Stack
                            key={e.id}
                            direction="row"
                            alignItems="center"
                            spacing={0.5}
                          >
                            <ArrowRight size={14} />
                            <Chip
                              size="small"
                              label={STATE_LABELS[e.to_state as TaskState] ?? e.to_state}
                              onDelete={() => deleteMut.mutate(e.id)}
                            />
                          </Stack>
                        ))
                      )}
                    </Stack>
                  );
                })}
              </Stack>
            )}
          </Paper>

          {deadEnds.length > 0 && (
            <Alert severity="warning" icon={<AlertTriangle size={16} />} sx={{ mb: 3 }}>
              {t("p.ops.workflow.deadEnds", {
                states: deadEnds.map((s) => STATE_LABELS[s]).join(", "),
              })}
            </Alert>
          )}

          {/* Añadir transición */}
          <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
            <Typography variant="subtitle2" fontWeight={700} mb={1.5}>
              {t("p.ops.workflow.newTransition")}
            </Typography>
            <Stack
              direction="row"
              spacing={1.5}
              alignItems="center"
              flexWrap="wrap"
              useFlexGap
            >
              <TextField
                select
                size="small"
                label={t("p.ops.workflow.from")}
                value={from}
                onChange={(e) => setFrom(e.target.value as TaskState)}
                sx={{ minWidth: 160 }}
              >
                {STATES.map((s) => (
                  <MenuItem key={s} value={s}>
                    {STATE_LABELS[s]}
                  </MenuItem>
                ))}
              </TextField>
              <ArrowRight size={16} />
              <TextField
                select
                size="small"
                label={t("p.ops.workflow.to")}
                value={to}
                onChange={(e) => setTo(e.target.value as TaskState)}
                sx={{ minWidth: 160 }}
              >
                {STATES.filter((s) => s !== from).map((s) => (
                  <MenuItem key={s} value={s}>
                    {STATE_LABELS[s]}
                  </MenuItem>
                ))}
              </TextField>
              <Button
                variant="contained"
                startIcon={<Plus size={15} />}
                disabled={!from || !to || createMut.isPending}
                onClick={() => createMut.mutate()}
              >
                {t("p.ops.workflow.add")}
              </Button>
            </Stack>
          </Paper>

          {/* Vista de tabla accesible */}
          <Paper variant="outlined" sx={{ overflowX: "auto" }}>
            <Table size="small">
              <caption
                style={{
                  textAlign: "left",
                  padding: 8,
                  opacity: 0.7,
                  captionSide: "bottom",
                }}
              >
                {t("p.ops.workflow.tableCaption")}
              </caption>
              <TableHead>
                <TableRow>
                  <TableCell>{t("p.ops.workflow.from")}</TableCell>
                  <TableCell></TableCell>
                  <TableCell>{t("p.ops.workflow.to")}</TableCell>
                  <TableCell align="right">{t("p.ops.actions")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {edges.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell>
                      {STATE_LABELS[e.from_state as TaskState] ?? e.from_state}
                    </TableCell>
                    <TableCell>
                      <ArrowRight size={14} />
                    </TableCell>
                    <TableCell>
                      {STATE_LABELS[e.to_state as TaskState] ?? e.to_state}
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title={t("p.ops.workflow.deleteTransition")}>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={async () => {
                            if (
                              await confirm(
                                t("p.ops.workflow.confirmDelete", {
                                  from: STATE_LABELS[e.from_state as TaskState],
                                  to: STATE_LABELS[e.to_state as TaskState],
                                }),
                                { confirmLabel: t("common.delete") },
                              )
                            )
                              deleteMut.mutate(e.id);
                          }}
                        >
                          <Trash2 size={15} />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
                {edges.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4}>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        textAlign="center"
                        py={2}
                      >
                        {t("p.ops.workflow.emptyTable")}
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Paper>
        </>
      )}
    </Box>
  );
}
