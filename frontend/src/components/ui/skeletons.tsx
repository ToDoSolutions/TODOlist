import { Box, Skeleton, Stack } from "@mui/material";

/** Skeletons que replican la forma del contenido real (Linear/Todoist style). */

export function PageHeaderSkeleton() {
  return (
    <Box mb={3}>
      <Skeleton variant="text" width={140} height={16} sx={{ mb: 0.5 }} />
      <Skeleton variant="text" width={260} height={36} />
    </Box>
  );
}

/** Filas de lista de tareas (checkbox + título + metadatos). */
export function TaskListSkeleton({ rows = 7 }: { rows?: number }) {
  return (
    <Stack spacing={0.5} aria-hidden>
      {Array.from({ length: rows }, (_, i) => (
        <Box
          key={i}
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1.5,
            px: 1.5,
            py: 1,
            borderRadius: 2,
            border: 1,
            borderColor: "divider",
          }}
        >
          <Skeleton variant="circular" width={20} height={20} />
          <Box flex={1}>
            <Skeleton variant="text" width={`${45 + ((i * 17) % 40)}%`} height={20} />
            <Skeleton variant="text" width={`${25 + ((i * 11) % 20)}%`} height={14} />
          </Box>
          <Skeleton variant="rounded" width={56} height={20} />
          <Skeleton variant="circular" width={20} height={20} />
        </Box>
      ))}
    </Stack>
  );
}

/** Columnas kanban (cabecera + tarjetas). */
export function KanbanSkeleton({ columns = 4 }: { columns?: number }) {
  return (
    <Box sx={{ display: "flex", gap: 2, overflow: "hidden" }} aria-hidden>
      {Array.from({ length: columns }, (_, c) => (
        <Box key={c} sx={{ flex: 1, minWidth: 240 }}>
          <Stack direction="row" spacing={1} alignItems="center" mb={1}>
            <Skeleton variant="rounded" width={90} height={22} />
            <Skeleton variant="circular" width={18} height={18} />
          </Stack>
          <Stack spacing={1}>
            {Array.from({ length: 2 + (c % 3) }, (_, i) => (
              <Skeleton key={i} variant="rounded" height={76} sx={{ borderRadius: 2 }} />
            ))}
          </Stack>
        </Box>
      ))}
    </Box>
  );
}

/** Grid de cards (proyectos, dashboards, integraciones). */
export function CardGridSkeleton({ cards = 6 }: { cards?: number }) {
  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
        gap: 2,
      }}
      aria-hidden
    >
      {Array.from({ length: cards }, (_, i) => (
        <Box key={i} sx={{ p: 2, borderRadius: 3, border: 1, borderColor: "divider" }}>
          <Stack direction="row" spacing={1.5} alignItems="center" mb={1.5}>
            <Skeleton variant="circular" width={36} height={36} />
            <Skeleton variant="text" width="55%" height={24} />
          </Stack>
          <Skeleton variant="text" width="85%" />
          <Skeleton variant="text" width="60%" />
          <Skeleton variant="rounded" height={6} sx={{ mt: 1.5 }} />
        </Box>
      ))}
    </Box>
  );
}

/** Tabla (cabecera + filas). */
export function TableSkeleton({ rows = 8, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <Box aria-hidden>
      <Stack direction="row" spacing={2} sx={{ px: 1.5, py: 1 }}>
        {Array.from({ length: cols }, (_, i) => (
          <Skeleton key={i} variant="text" width={`${100 / cols}%`} height={20} />
        ))}
      </Stack>
      {Array.from({ length: rows }, (_, r) => (
        <Stack
          key={r}
          direction="row"
          spacing={2}
          sx={{ px: 1.5, py: 1.2, borderTop: 1, borderColor: "divider" }}
        >
          {Array.from({ length: cols }, (_, c) => (
            <Skeleton key={c} variant="text" width={`${100 / cols}%`} height={18} />
          ))}
        </Stack>
      ))}
    </Box>
  );
}

/** Dashboard: KPIs arriba + widgets. */
export function DashboardSkeleton() {
  return (
    <Box aria-hidden>
      <PageHeaderSkeleton />
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 2,
          mb: 3,
        }}
      >
        {Array.from({ length: 4 }, (_, i) => (
          <Box key={i} sx={{ p: 2, borderRadius: 3, border: 1, borderColor: "divider" }}>
            <Skeleton variant="text" width="60%" height={16} />
            <Skeleton variant="text" width="40%" height={36} />
          </Box>
        ))}
      </Box>
      <CardGridSkeleton cards={4} />
    </Box>
  );
}

/** Página genérica: header + lista. */
export function PageSkeleton({
  kind = "list",
}: {
  kind?: "list" | "kanban" | "grid" | "table";
}) {
  return (
    <Box>
      <PageHeaderSkeleton />
      {kind === "kanban" ? (
        <KanbanSkeleton />
      ) : kind === "grid" ? (
        <CardGridSkeleton />
      ) : kind === "table" ? (
        <TableSkeleton />
      ) : (
        <TaskListSkeleton />
      )}
    </Box>
  );
}
