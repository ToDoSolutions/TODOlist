import { useMemo, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Stack,
  Paper,
  TextField,
  MenuItem,
  Chip,
  Alert,
} from "@mui/material";
import { ArrowRight, Link2, AlertTriangle } from "lucide-react";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState, ErrorState } from "../components/ui/states";
import { TaskListSkeleton } from "../components/ui/skeletons";
import { tasksApi, type TaskDependencies } from "../api/resources";
import { STATE_LABELS, type Task, type TaskState } from "../types";

const MAX_DEPTH = 4;

interface DepNode {
  task_id: number;
  title: string;
  state?: string;
  relation: string;
}

/**
 * Grafo de dependencias: bloqueantes a la izquierda, bloqueadas a la derecha.
 * Detecta ciclos transitivos (A bloquea B, B bloquea A) recorriendo la cadena
 * "blocks" hasta una profundidad limitada.
 */
export default function DependenciesPage() {
  const { t } = useTranslation();
  const [taskId, setTaskId] = useState<number | "">("");

  const { data: tasksData } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => tasksApi.list({}),
  });
  const tasks: Task[] = useMemo(
    () => (Array.isArray(tasksData) ? tasksData : []),
    [tasksData],
  );

  // Preselecciona la primera tarea que tenga relaciones (la primera si
  // ninguna tiene) — evita la pantalla "Selecciona una tarea" obligando
  // a un clic extra para ver algo.
  useEffect(() => {
    if (taskId !== "" || tasks.length === 0) return;
    let cancelled = false;
    (async () => {
      // Recorre en orden de id ascendente: el demo suele tener las
      // relaciones en las tareas más antiguas.
      const ordered = [...tasks].sort((a, b) => a.id - b.id);
      for (const task of ordered.slice(0, 50)) {
        try {
          const d = await tasksApi.dependencies(task.id);
          if (cancelled || taskId !== "") return;
          if (d.blocked_by.length > 0 || d.blocks.length > 0) {
            setTaskId(task.id);
            return;
          }
        } catch {
          continue;
        }
      }
      const first = tasks[0];
      if (!cancelled && first?.id != null) setTaskId(first.id);
    })();
    return () => {
      cancelled = true;
    };
  }, [tasks, taskId]);

  const { data: rootDeps, isLoading, isError, refetch } = useQuery({
    queryKey: ["task-dependencies", taskId],
    queryFn: () => tasksApi.dependencies(Number(taskId)),
    enabled: taskId !== "",
  });

  // BFS sobre aristas "blocks" para detectar si la cadena vuelve a la tarea raíz.
  // El resultado se etiqueta con la raíz: no hace falta resetear en el effect,
  // un ciclo de una tarea anterior se descarta al renderizar.
  const [cycleFor, setCycleFor] = useState<{ root: number; path: number[] } | null>(null);
  useEffect(() => {
    if (!rootDeps || taskId === "") return;
    const root = Number(taskId);
    let cancelled = false;
    (async () => {
      const visited = new Map<number, TaskDependencies>([[root, rootDeps]]);
      // cola: [id de tarea, camino hasta ella]
      const queue: [number, number[]][] = rootDeps.blocks.map((b) => [
        b.task_id,
        [root, b.task_id],
      ]);
      while (queue.length) {
        if (cancelled) return;
        const [id, path] = queue.shift()!;
        if (id === root) {
          setCycleFor({ root, path });
          return;
        }
        if (path.length > MAX_DEPTH + 1 || visited.has(id)) continue;
        try {
          const d = await tasksApi.dependencies(id);
          visited.set(id, d);
          for (const b of d.blocks) queue.push([b.task_id, [...path, b.task_id]]);
        } catch {
          continue; // sin acceso o borrada: no bloquea el análisis
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [rootDeps, taskId]);

  const cycle =
    cycleFor && taskId !== "" && cycleFor.root === Number(taskId) ? cycleFor.path : null;

  const nodeCard = (n: DepNode, color: "error" | "warning" | "default") => (
    <Paper
      key={`${n.task_id}-${n.relation}`}
      variant="outlined"
      sx={{ p: 1.5, cursor: "pointer", "&:hover": { borderColor: "primary.main" } }}
      onClick={() => setTaskId(n.task_id)}
    >
      <Stack direction="row" spacing={1} alignItems="center">
        <Chip
          size="small"
          label={t(`p.plan.dependencies.rel.${n.relation}`, {
            defaultValue: n.relation,
          })}
          color={color === "default" ? "default" : color}
          variant="outlined"
          sx={{ minWidth: 90 }}
        />
        <Box minWidth={0}>
          <Typography variant="body2" fontWeight={600} noWrap>
            #{n.task_id} · {n.title}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {STATE_LABELS[n.state as TaskState] ?? n.state}
          </Typography>
        </Box>
      </Stack>
    </Paper>
  );

  const rootTask = useMemo(
    () => tasks.find((task) => task.id === Number(taskId)),
    [tasks, taskId],
  );

  return (
    <Box>
      <PageHeader
        title={t("p.plan.dependencies.title")}
        description={t("p.plan.dependencies.desc")}
        breadcrumbs={[
          { label: t("p.plan.dependencies.breadcrumbProject") },
          { label: t("p.plan.dependencies.title") },
        ]}
      />

      <TextField
        select
        size="small"
        label={t("p.plan.dependencies.taskLabel")}
        value={taskId}
        onChange={(e) => setTaskId(e.target.value === "" ? "" : Number(e.target.value))}
        sx={{ minWidth: 320, mb: 3 }}
      >
        <MenuItem value="">{t("p.plan.dependencies.selectTask")}</MenuItem>
        {tasks.map((task) => (
          <MenuItem key={task.id} value={task.id}>
            #{task.id} · {task.title}
          </MenuItem>
        ))}
      </TextField>

      {taskId === "" ? (
        <EmptyState
          title={t("p.plan.dependencies.selectTask")}
          description={t("p.plan.dependencies.emptyDesc")}
          icon={<Link2 size={40} />}
        />
      ) : isLoading ? (
        <TaskListSkeleton rows={4} />
      ) : isError || !rootDeps ? (
        <ErrorState
          title={t("p.plan.dependencies.loadError")}
          onRetry={() => void refetch()}
        />
      ) : (
        <>
          {rootDeps.is_blocked && (
            <Alert severity="error" sx={{ mb: 2 }} icon={<AlertTriangle size={16} />}>
              {t("p.plan.dependencies.blockedBy", {
                count: rootDeps.blocked_by.length,
              })}
            </Alert>
          )}
          {cycle && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              {t("p.plan.dependencies.cycleDetected", {
                path: cycle.map((id) => `#${id}`).join(" → "),
              })}
            </Alert>
          )}

          <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="stretch">
            {/* Bloqueantes */}
            <Paper variant="outlined" sx={{ flex: 1, p: 2 }}>
              <Typography variant="subtitle2" fontWeight={700} mb={1.5}>
                {t("p.plan.dependencies.blockedByCount", {
                  count: rootDeps.blocked_by.length,
                })}
              </Typography>
              <Stack spacing={1}>
                {rootDeps.blocked_by.map((n) => nodeCard(n, "error"))}
                {rootDeps.blocked_by.length === 0 && (
                  <Typography variant="caption" color="text.secondary">
                    {t("p.plan.dependencies.nothingBlocks")}
                  </Typography>
                )}
              </Stack>
            </Paper>

            {/* Nodo central */}
            <Stack
              justifyContent="center"
              alignItems="center"
              spacing={1}
              sx={{ minWidth: 200 }}
            >
              <ArrowRight
                size={18}
                style={{ transform: "rotate(180deg)", opacity: 0.5 }}
              />
              <Paper
                sx={{ p: 2, textAlign: "center", border: 2, borderColor: "primary.main" }}
              >
                <Typography variant="subtitle2" fontWeight={700}>
                  #{rootDeps.task_id} ·{" "}
                  {rootTask?.title ?? t("p.plan.dependencies.taskLabel")}
                </Typography>
                {rootTask && (
                  <Chip
                    size="small"
                    label={STATE_LABELS[rootTask.state]}
                    sx={{ mt: 0.5 }}
                  />
                )}
              </Paper>
              <ArrowRight size={18} style={{ opacity: 0.5 }} />
            </Stack>

            {/* Bloqueadas por ella */}
            <Paper variant="outlined" sx={{ flex: 1, p: 2 }}>
              <Typography variant="subtitle2" fontWeight={700} mb={1.5}>
                {t("p.plan.dependencies.blocksCount", {
                  count: rootDeps.blocks.length,
                })}
              </Typography>
              <Stack spacing={1}>
                {rootDeps.blocks.map((n) => nodeCard(n, "warning"))}
                {rootDeps.blocks.length === 0 && (
                  <Typography variant="caption" color="text.secondary">
                    {t("p.plan.dependencies.blocksNothing")}
                  </Typography>
                )}
              </Stack>
            </Paper>
          </Stack>

          {rootDeps.related.length > 0 && (
            <Paper variant="outlined" sx={{ mt: 2, p: 2 }}>
              <Typography variant="subtitle2" fontWeight={700} mb={1}>
                {t("p.plan.dependencies.relatedCount", {
                  count: rootDeps.related.length,
                })}
              </Typography>
              <Stack spacing={1}>
                {rootDeps.related.map((n) => nodeCard(n, "default"))}
              </Stack>
            </Paper>
          )}
        </>
      )}
    </Box>
  );
}
