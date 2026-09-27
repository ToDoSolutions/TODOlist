import { formatDateTime } from "../lib/dates";
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
  Alert,
  useTheme,
} from "@mui/material";
import { ScrollText } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { collaborationApi } from "../api/resources";
import type { AuditLogEntry } from "../types";
import { useTranslation } from "react-i18next";

const ACTION_KEYS: Record<string, string> = {
  login: "p.admin.audit.actions.login",
  logout: "p.admin.audit.actions.logout",
  login_failed: "p.admin.audit.actions.login_failed",
  create: "p.admin.audit.actions.create",
  update: "p.admin.audit.actions.update",
  delete: "p.admin.audit.actions.delete",
  permission_change: "p.admin.audit.actions.permission_change",
  role_change: "p.admin.audit.actions.role_change",
  export: "p.admin.audit.actions.export",
  settings_change: "p.admin.audit.actions.settings_change",
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
  const { t } = useTranslation();
  const theme = useTheme();
  const [actionFilter, setActionFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("");

  const { data, isLoading, isError } = useQuery({
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
        <ScrollText size={24} style={{ color: theme.palette.secondary.main }} />
        <Typography variant="h5" fontWeight={700}>
          {t("nav.audit")}
        </Typography>
      </Stack>

      {/* Filtros */}
      <Stack direction="row" spacing={2} mb={2}>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>{t("p.admin.audit.actionLabel")}</InputLabel>
          <Select
            value={actionFilter}
            label={t("p.admin.audit.actionLabel")}
            onChange={(e) => setActionFilter(e.target.value)}
          >
            <MenuItem value="">{t("p.admin.audit.allFem")}</MenuItem>
            {Object.entries(ACTION_KEYS).map(([k, key]) => (
              <MenuItem key={k} value={k}>
                {t(key)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>{t("p.admin.audit.resourceLabel")}</InputLabel>
          <Select
            value={resourceFilter}
            label={t("p.admin.audit.resourceLabel")}
            onChange={(e) => setResourceFilter(e.target.value)}
          >
            <MenuItem value="">{t("p.admin.audit.allMasc")}</MenuItem>
            <MenuItem value="task">{t("p.admin.audit.res.task")}</MenuItem>
            <MenuItem value="project">{t("p.admin.audit.res.project")}</MenuItem>
            <MenuItem value="user">{t("p.admin.audit.res.user")}</MenuItem>
            <MenuItem value="team">{t("p.admin.audit.res.team")}</MenuItem>
          </Select>
        </FormControl>
      </Stack>

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {t("p.admin.audit.loadError")}
        </Alert>
      )}
      {isLoading ? (
        <Box display="flex" justifyContent="center" py={5}>
          <CircularProgress />
        </Box>
      ) : logs.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Typography color="text.secondary">{t("p.admin.audit.empty")}</Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>{t("p.admin.audit.colDate")}</TableCell>
                <TableCell>{t("p.admin.audit.actionLabel")}</TableCell>
                <TableCell>{t("p.admin.audit.resourceLabel")}</TableCell>
                <TableCell>{t("p.admin.audit.colDetail")}</TableCell>
                <TableCell>IP</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {logs.map((log: AuditLogEntry) => (
                <TableRow key={log.id} hover>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">
                      {formatDateTime(log.created_at)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={t(ACTION_KEYS[log.action] || log.action)}
                      sx={{
                        height: 20,
                        fontSize: 10,
                        bgcolor: ACTION_COLORS[log.action] || "#757575",
                        color: "common.white",
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
                        <Typography
                          component="span"
                          variant="caption"
                          color="text.secondary"
                          display="block"
                        >
                          {JSON.stringify(log.old_values)} →{" "}
                          {JSON.stringify(log.new_values)}
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
