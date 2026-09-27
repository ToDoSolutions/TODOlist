import { useEffect, useRef, useState } from "react";
import { useWindowVirtualizer } from "@tanstack/react-virtual";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Box, Checkbox, Divider, IconButton, Stack, Typography } from "@mui/material";
import { GripVertical } from "lucide-react";
import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  closestCenter,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import TaskListItem from "./TaskListItem";
import { taskOrderApi } from "../api/featTask3";
import { notify } from "../notify";
import type { Task } from "../types";

const VIRTUALIZE_THRESHOLD = 60;
const ESTIMATED_ROW = 72;

/** Grupo de tareas bajo una cabecera (p.ej. una sección de proyecto).
 *  `id === null` representa el grupo "sin sección". */
export interface TaskGroup {
  id: number | null;
  name: string;
  tasks: Task[];
}

interface Props {
  tasks: Task[];
  selected: Set<number>;
  /**
   * Toggle de selección. `shiftKey` llega cuando el usuario hace
   * Shift+clic en el checkbox: el padre selecciona el rango inclusivo
   * entre el último id clicado y el actual.
   */
  toggleSelect: (id: number, shiftKey?: boolean) => void;
  onEdit: (t: Task) => void;
  /**
   * Ordenación manual (ordering=position): activa drag & drop por fila.
   * Solo efectivo por debajo de VIRTUALIZE_THRESHOLD — sobre el umbral la
   * lista se virtualiza (filas en absolute) y el reorden queda desactivado.
   */
  reorderable?: boolean;
  /**
   * Agrupación por secciones: cuando se pasa, la lista se pinta por
   * grupos con cabecera (nombre + contador + divisor) en vez de plana.
   * Desactiva la virtualización igual que `reorderable`.
   */
  groups?: TaskGroup[];
  /** Fila con foco de teclado (navegación j/k): ring + scrollIntoView. */
  focusedId?: number | null;
}

function Row({
  task,
  selected,
  toggleSelect,
  onEdit,
  focused = false,
}: {
  task: Task;
  selected: boolean;
  toggleSelect: (id: number, shiftKey?: boolean) => void;
  onEdit: (t: Task) => void;
  focused?: boolean;
}) {
  return (
    <Box
      data-task-id={task.id}
      sx={{
        display: "flex",
        alignItems: "flex-start",
        gap: 0.5,
        borderRadius: 2,
        outline: focused ? "2px solid" : "none",
        outlineColor: "primary.main",
        outlineOffset: 1,
        "&:hover .select-checkbox": { opacity: 1 },
      }}
    >
      <Checkbox
        className="select-checkbox"
        size="small"
        checked={selected}
        onClick={(e) => toggleSelect(task.id, e.shiftKey)}
        sx={{
          mt: 0.5,
          opacity: selected ? 1 : 0,
          transition: "opacity 0.2s",
          color: "primary.main",
          "&.Mui-checked": { opacity: 1 },
        }}
      />
      <Box sx={{ flex: 1 }}>
        <TaskListItem task={task} onEdit={onEdit} />
      </Box>
    </Box>
  );
}

/**
 * Fila reordenable: el handle (⋮⋮) concentra listeners/attributes de
 * useSortable para no secuestrar clics ni la selección de texto del resto
 * de la fila. Aparece en hover/focus (teclado) como el checkbox.
 */
function SortableRow({
  task,
  selected,
  toggleSelect,
  onEdit,
  focused = false,
}: {
  task: Task;
  selected: boolean;
  toggleSelect: (id: number, shiftKey?: boolean) => void;
  onEdit: (t: Task) => void;
  focused?: boolean;
}) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: task.id });

  return (
    <Box
      ref={setNodeRef}
      data-task-id={task.id}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
      }}
      sx={{
        display: "flex",
        alignItems: "flex-start",
        gap: 0.5,
        opacity: isDragging ? 0.55 : 1,
        borderRadius: 2,
        outline: focused ? "2px solid" : "none",
        outlineColor: "primary.main",
        outlineOffset: 1,
        "&:hover .select-checkbox, &:hover .drag-handle": { opacity: 1 },
      }}
    >
      <IconButton
        className="drag-handle"
        size="small"
        aria-label={t("p.taskx.dragHandle")}
        {...attributes}
        {...listeners}
        sx={{
          mt: 0.75,
          px: 0.25,
          cursor: isDragging ? "grabbing" : "grab",
          touchAction: "none",
          opacity: isDragging ? 1 : 0,
          transition: "opacity 0.2s",
          color: "text.secondary",
          "&:focus-visible": { opacity: 1 },
        }}
      >
        <GripVertical size={15} />
      </IconButton>
      <Checkbox
        className="select-checkbox"
        size="small"
        checked={selected}
        onClick={(e) => toggleSelect(task.id, e.shiftKey)}
        sx={{
          mt: 0.5,
          opacity: selected ? 1 : 0,
          transition: "opacity 0.2s",
          color: "primary.main",
          "&.Mui-checked": { opacity: 1 },
        }}
      />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <TaskListItem task={task} onEdit={onEdit} />
      </Box>
    </Box>
  );
}

/**
 * Variante reordenable (patrón Todoist): mantiene una copia local del orden
 * sincronizada con las props; al soltar se persiste el orden completo con
 * POST /tasks/reorder/ (optimista) y la invalidación de ["tasks"] resincroniza.
 */
function SortableRows({
  tasks,
  selected,
  toggleSelect,
  onEdit,
  focusedId,
}: Omit<Props, "reorderable" | "groups">) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  // Copia local optimista del orden; se reajusta en render cuando cambian
  // las props (patrón "adjusting state", sin setState en effect).
  const [ordered, setOrdered] = useState<Task[]>(tasks);
  const [prevTasks, setPrevTasks] = useState<Task[]>(tasks);
  if (prevTasks !== tasks) {
    setPrevTasks(tasks);
    setOrdered(tasks);
  }

  // Mismo patrón de sensores que KanbanBoard (pointer con umbral +
  // teclado); aquí el teclado usa sortableKeyboardCoordinates para el handle.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const reorderMut = useMutation({
    mutationFn: (taskIds: number[]) => taskOrderApi.reorder(taskIds),
    onError: () => {
      // Revertir la copia optimista al último orden conocido del servidor
      setOrdered(tasks);
      setPrevTasks(tasks);
      notify.error(t("p.taskx.reorder.error"));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const from = ordered.findIndex((task) => task.id === active.id);
    const to = ordered.findIndex((task) => task.id === over.id);
    if (from < 0 || to < 0) return;
    const next = arrayMove(ordered, from, to);
    setOrdered(next);
    reorderMut.mutate(next.map((task) => task.id));
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={onDragEnd}
    >
      <SortableContext
        items={ordered.map((task) => task.id)}
        strategy={verticalListSortingStrategy}
      >
        <Stack spacing={1}>
          {ordered.map((task) => (
            <SortableRow
              key={task.id}
              task={task}
              selected={selected.has(task.id)}
              toggleSelect={toggleSelect}
              onEdit={onEdit}
              focused={task.id === focusedId}
            />
          ))}
        </Stack>
      </SortableContext>
    </DndContext>
  );
}

/**
 * Variante agrupada (secciones de proyecto): cada grupo se pinta con una
 * cabecera (nombre + nº de tareas + divisor sutil) y sus filas debajo.
 * Sin virtualización ni drag & drop — igual que `reorderable`, el modo
 * agrupado usa la lista simple.
 */
function GroupedRows({
  groups,
  selected,
  toggleSelect,
  onEdit,
  focusedId,
}: {
  groups: TaskGroup[];
  selected: Set<number>;
  toggleSelect: (id: number, shiftKey?: boolean) => void;
  onEdit: (t: Task) => void;
  focusedId?: number | null;
}) {
  const { t } = useTranslation();
  return (
    <Stack spacing={2}>
      {groups.map((group) => (
        <Box key={group.id ?? "none"}>
          <Stack
            direction="row"
            alignItems="center"
            spacing={1}
            sx={{ px: 0.5, mb: 0.5 }}
          >
            <Typography variant="subtitle2" fontWeight={700} noWrap>
              {group.name}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {t("p.taskx.sections.count", { count: group.tasks.length })}
            </Typography>
            <Divider sx={{ flex: 1 }} aria-hidden />
          </Stack>
          <Stack spacing={1}>
            {group.tasks.map((task) => (
              <Row
                key={task.id}
                task={task}
                selected={selected.has(task.id)}
                toggleSelect={toggleSelect}
                onEdit={onEdit}
                focused={task.id === focusedId}
              />
            ))}
          </Stack>
        </Box>
      ))}
    </Stack>
  );
}

/**
 * Lista de tareas: render simple para listas cortas, virtualizada
 * (windowing) cuando supera el umbral para mantener 60fps con miles
 * de elementos. Con `reorderable` (orden manual) usa filas sortables
 * con drag & drop — solo bajo el umbral. Con `groups` pinta cabeceras
 * de sección y desactiva tanto la virtualización como el reorden.
 */
export default function TaskRows({
  tasks,
  selected,
  toggleSelect,
  onEdit,
  reorderable = false,
  groups,
  focusedId,
}: Props) {
  const listRef = useRef<HTMLDivElement>(null);
  const virtualize = tasks.length > VIRTUALIZE_THRESHOLD;
  const [scrollMargin, setScrollMargin] = useState(0);

  useEffect(() => {
    if (virtualize && listRef.current) {
      setScrollMargin(listRef.current.offsetTop);
    }
  }, [virtualize]);

  const virtualizer = useWindowVirtualizer({
    count: virtualize ? tasks.length : 0,
    estimateSize: () => ESTIMATED_ROW,
    overscan: 8,
    scrollMargin,
  });

  if (groups) {
    return (
      <GroupedRows
        groups={groups}
        selected={selected}
        toggleSelect={toggleSelect}
        onEdit={onEdit}
        focusedId={focusedId}
      />
    );
  }

  if (reorderable && !virtualize) {
    return (
      <SortableRows
        tasks={tasks}
        selected={selected}
        toggleSelect={toggleSelect}
        onEdit={onEdit}
        focusedId={focusedId}
      />
    );
  }

  if (!virtualize) {
    return (
      <Stack spacing={1}>
        {tasks.map((t) => (
          <Row
            key={t.id}
            task={t}
            selected={selected.has(t.id)}
            toggleSelect={toggleSelect}
            onEdit={onEdit}
            focused={t.id === focusedId}
          />
        ))}
      </Stack>
    );
  }

  return (
    <Box
      ref={listRef}
      sx={{
        height: virtualizer.getTotalSize(),
        position: "relative",
      }}
    >
      {virtualizer.getVirtualItems().map((vi) => {
        const t = tasks[vi.index];
        if (!t) return null;
        return (
          <Box
            key={t.id}
            data-index={vi.index}
            ref={virtualizer.measureElement}
            sx={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              pb: 1,
              transform: `translateY(${vi.start - scrollMargin}px)`,
            }}
          >
            <Row
              task={t}
              selected={selected.has(t.id)}
              toggleSelect={toggleSelect}
              onEdit={onEdit}
              focused={t.id === focusedId}
            />
          </Box>
        );
      })}
    </Box>
  );
}
