import { useState } from "react";
import {
  Box,
  Typography,
  Paper,
  Stack,
  Chip,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
} from "@mui/material";
import { ScrollText } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { collaborationApi } from "../api/resources";

const ACTION_LABELS: Record<string, string> = {
  login: "Login",
  logout: "Logout",
  login_failed: "Login fallido",
  create: "Creación",
  update: "Actualización",
  delete: "Eliminación",
  permission_change: "Cambio de permisos",
  role_change: "Cambio de rol",
  export: "Exportación",
  settings_change: "Cambio de config",
};

const ACTION_COLORS: Record<string, string> = {
  login: "#43a047",
  logout: "#757575",
  login_failed: "#d32f2f",
  create: "#1976d2",
  update: "#f57c00",
  delete: "#d32f2f",
  permission_change: "#7b1fa2",
  role_change: "#7b1fa2",
  export: "#0288d1",
  settings_change: "#f57c00",
};

export default function AuditPage() {
  const [actionFilter, setActionFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["audit-logs", actionFilter, resourceFilter],
    queryFn: () =>
      collaborationApi.auditLogs.list({
        action: actionFilter || undefined,
        resource_type: resourceFilter || undefined,
      }),
  });

  const logs = data?.results || data || [];

  return (
    <Box maxWidth={1000} mx="auto">
      <Stack direction="row" alignItems="center" spacing={1} mb={3}>
        <ScrollText size={24} color="#7c4dff" />
        <Typography variant="h5" fontWeight={700}>Auditoría</Typography>
      </Stack>

      {/* Filtros */}
      <Stack direction="row" spacing={2} mb={2}>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Acción</InputLabel>
          <Select
            value={actionFilter}
            label="Acción"
            onChange={(e) => setActionFilter(e.target.value)}
          >
            <MenuItem value="">Todas</MenuItem>
            {Object.entries(ACTION_LABELS).map(([k, v]) => (
              <MenuItem key={k} value={k}>{v}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Recurso</InputLabel>
          <Select
            value={resourceFilter}
            label="Recurso"
            onChange={(e) => setResourceFilter(e.target.value)}
          >
            <MenuItem value="">Todos</MenuItem>
            <MenuItem value="task">Tarea</MenuItem>
            <MenuItem value="project">Proyecto</MenuItem>
            <MenuItem value="user">Usuario</MenuItem>
            <MenuItem value="team">Equipo</MenuItem>
          </Select>
        </FormControl>
      </Stack>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={5}>
          <CircularProgress />
        </Box>
      ) : logs.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Typography color="text.secondary">
            No hay registros de auditoría.
          </Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>Fecha</TableCell>
                <TableCell>Acción</TableCell>
                <TableCell>Recurso</TableCell>
                <TableCell>Detalle</TableCell>
                <TableCell>IP</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {logs.map((log: any) => (
                <TableRow key={log.id} hover>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">
                      {new Date(log.created_at).toLocaleString("es-ES")}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={ACTION_LABELS[log.action] || log.action}
                      sx={{
                        height: 20,
                        fontSize: 10,
                        bgcolor: ACTION_COLORS[log.action] || "#757575",
                        color: "#fff",
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {log.resource_type}
                      {log.resource_id && `:${log.resource_id}`}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" noWrap sx={{ maxWidth: 300 }}>
                      {log.resource_name}
                      {log.old_values && Object.keys(log.old_values).length > 0 && (
                        <Typography component="span" variant="caption" color="text.secondary" display="block">
                          {JSON.stringify(log.old_values)} → {JSON.stringify(log.new_values)}
                        </Typography>
                      )}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">
                      {log.ip_address || "—"}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
