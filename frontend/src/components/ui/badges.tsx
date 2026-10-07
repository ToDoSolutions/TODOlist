import { Chip, ChipProps, Avatar, AvatarProps, Tooltip } from "@mui/material";
import type { JSX } from "react";
import {
  AlertCircle,
  Archive,
  Ban,
  CheckCircle2,
  Circle,
  Clock,
  Eye,
  Pause,
  PlayCircle,
  XCircle,
} from "lucide-react";

/* Estado: color + icono + texto — nunca solo color (WCAG 1.4.1) */
const STATE_MAP: Record<
  string,
  { label: string; color: ChipProps["color"]; icon: JSX.Element }
> = {
  backlog: { label: "Backlog", color: "default", icon: <Circle size={12} /> },
  pending: { label: "Pendiente", color: "info", icon: <Clock size={12} /> },
  in_progress: { label: "En progreso", color: "primary", icon: <PlayCircle size={12} /> },
  review: { label: "Revisión", color: "secondary", icon: <Eye size={12} /> },
  blocked: { label: "Bloqueada", color: "warning", icon: <Ban size={12} /> },
  completed: { label: "Completada", color: "success", icon: <CheckCircle2 size={12} /> },
  cancelled: { label: "Cancelada", color: "default", icon: <XCircle size={12} /> },
  archived: { label: "Archivada", color: "default", icon: <Archive size={12} /> },
  paused: { label: "Pausada", color: "default", icon: <Pause size={12} /> },
  error: { label: "Error", color: "error", icon: <AlertCircle size={12} /> },
};

export function StatusBadge({
  state,
  size = "small",
}: {
  state: string;
  size?: ChipProps["size"];
}) {
  const s = STATE_MAP[state] ?? {
    label: state,
    color: "default" as const,
    icon: <Circle size={12} />,
  };
  return (
    <Chip
      size={size}
      color={s.color}
      variant="outlined"
      icon={s.icon}
      label={s.label}
      sx={{ fontWeight: 500 }}
    />
  );
}

const PRIORITY_MAP: Record<number, { label: string; color: ChipProps["color"] }> = {
  0: { label: "Sin prioridad", color: "default" },
  1: { label: "Muy baja", color: "default" },
  2: { label: "Baja", color: "info" },
  3: { label: "Media", color: "primary" },
  4: { label: "Alta", color: "warning" },
  5: { label: "Urgente", color: "error" },
};

export function PriorityBadge({
  priority,
  size = "small",
}: {
  priority: number;
  size?: ChipProps["size"];
}) {
  const p = PRIORITY_MAP[priority] ?? PRIORITY_MAP[0]!;
  // Barras de prioridad: redundancia visual además del color
  const bars = "▂▄▆█".slice(0, Math.max(1, Math.min(4, priority)));
  return (
    <Chip
      size={size}
      color={p.color}
      variant="outlined"
      label={`${bars} ${p.label}`}
      sx={{ fontWeight: 500, fontFamily: "monospace" }}
    />
  );
}

export function UserAvatar({
  email,
  size = 28,
  ...props
}: { email?: string; size?: number } & AvatarProps) {
  const initial = email?.[0]?.toUpperCase() ?? "?";
  return (
    <Tooltip title={email ?? ""}>
      <Avatar
        sx={{ width: size, height: size, bgcolor: "primary.main", fontSize: size * 0.45 }}
        {...props}
      >
        {initial}
      </Avatar>
    </Tooltip>
  );
}
