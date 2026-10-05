import { formatDateTime } from "../lib/dates";
import { useState } from "react";
import { TableSkeleton } from "../components/ui/skeletons";
import PageHeader from "../components/ui/PageHeader";
import { ErrorState } from "../components/ui/states";
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
  Button,
  useTheme,
} from "@mui/material";
import { ScrollText, Download } from "lucide-react";
import { saveAs } from "file-saver";
import { useQuery } from "@tanstack/react-query";
import { collaborationApi } from "../api/resources";
import type { AuditLogEntry, TaskState, TaskPriority } from "../types";
import { STATE_LABELS, PRIORITY_LABELS } from "../types";
import { useTranslation } from "react-i18next";

const FIELD_LABELS: Record<string, string> = {
  state: "estado",
  description: "descripción",
  title: "título",
  priority: "prioridad",
  due_date: "fecha límite",
  assignee: "asignado",
  name: "nombre",
  role: "rol",
};

/** Humaniza el diff old→new del audit log: state/priority vienen como
 * claves crudas ("in_progress", 2) y se traducen a las etiquetas UI. */
function humanDiff(values: Record<string, unknown> | undefined): string {
  if (!values || Object.keys(values).length === 0) return "";
  return Object.entries(values)
    .map(([k, v]) => {
      let label = String(v);
      if (k === "state" && typeof v === "string" && v in STATE_LABELS)
        label = STATE_LABELS[v as TaskState];
      else if (k === "priority" && v != null)
        label = PRIORITY_LABELS[Number(v) as TaskPriority] ?? String(v);
      return `${FIELD_LABELS[k] ?? k}: ${label}`;
    })
    .join(", ");
}

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

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["audit-logs", actionFilter, resourceFilter],
    queryFn: () =>
      collaborationApi.auditLogs.list({
        action: actionFilter || undefined,
        resource_type: resourceFilter || undefined,
      }),
  });

  const logs = data ?? [];

  const exportLogs = async (fmt: "csv" | "jsonl") => {
    const blob = await collaborationApi.auditLogs.export(fmt);
    saveAs(
      blob,
      `audit-logs-${new Date().toISOString().slice(0, 10)}.${fmt === "jsonl" ? "jsonl" : "csv"}`,
    );
  };

  return (
    <Box maxWidth={1000} mx="auto">
      <PageHeader
        title={
          <>
            <ScrollText size={22} style={{ color: theme.palette.secondary.main, verticalAlign: "text-bottom", marginRight: 8 }} />
            {t("nav.audit")}
          </>
        }
        actions={
          <>
            <Button
              size="small"
              variant="outlined"
              startIcon={<Download size={14} />}
              onClick={() => exportLogs("csv")}
            >
              CSV
            </Button>
            <Button
              size="small"
              variant="outlined"
              startIcon={<Download size={14} />}
              onClick={() => exportLogs("jsonl")}
            >
              JSONL
            </Button>
          </>
        }
      />

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
        <ErrorState
          title={t("p.admin.audit.loadError")}
          onRetry={() => void refetch()}
        />
      )}
      {isLoading ? (
        <TableSkeleton />
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
                          {humanDiff(log.old_values)} →{" "}
                          {humanDiff(log.new_values)}
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