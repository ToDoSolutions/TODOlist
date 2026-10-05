import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Box,
  Button,
  Typography,
  Paper,
  Chip,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  ToggleButtonGroup,
  ToggleButton,
  Alert,
  Tooltip,
} from "@mui/material";
import { Zap, RefreshCw, Webhook, ListChecks } from "lucide-react";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/states";
import { TableSkeleton } from "../components/ui/skeletons";
import { formatDateTime } from "../lib/dates";
import { automationsApi, syncOperationsApi, outgoingWebhooksApi } from "../api/resources";

interface JobRow {
  key: string;
  kind: "automation" | "sync" | "webhook";
  label: string;
  status: string;
  detail: string;
  date: string;
}

const KIND_META = {
  automation: { icon: <Zap size={14} />, label: "p.admin.jobs.kind.automation" },
  sync: { icon: <RefreshCw size={14} />, label: "p.admin.jobs.kind.sync" },
  webhook: { icon: <Webhook size={14} />, label: "p.admin.jobs.kind.webhook" },
};

import { PRIORITY_LABELS, STATE_LABELS, type TaskPriority, type TaskState } from "../types";
import type { TFunction } from "i18next";

/** Humaniza el action_result de una automatización: {"priority":0} →
 * "prioridad: P0 Crítica" en vez del JSON crudo. También traduce
 * valores de estado ("moved_to_in_progress" → "moved_to_in_progress"
 * pasa por STATE_LABELS si es un estado conocido). */
function humanizeActionResult(
  result: Record<string, unknown>,
  t: TFunction,
): string {
  return Object.entries(result)
    .map(([k, v]) => {
      let val = String(v);
      if (k === "priority" && v != null) {
        val = PRIORITY_LABELS[Number(v) as TaskPriority] ?? val;
      } else if (typeof v === "string" && v in STATE_LABELS) {
        val = STATE_LABELS[v as TaskState];
      } else if (typeof v === "string" && /^[a-z_]+$/.test(v)) {
        val = t(`p.admin.jobs.value.${v}`, v.replace(/_/g, " "));
      }
      const key = t(`p.admin.jobs.field.${k}`, k);
      return `${key}: ${val}`;
    })
    .join(", ");
}

const STATUS_COLOR: Record<string, "success" | "error" | "warning" | "default" | "info"> =
  {
    success: "success",
    applied: "success",
    processed: "success",
    completed: "success",
    failed: "error",
    rejected: "error",
    dead_letter: "error",
    conflict: "warning",
    retrying: "warning",
    skipped: "default",
    pending: "info",
  };

/** Centro de trabajos: vista unificada de los procesos en segundo plano
 *  (automatizaciones, sync offline, entregas de webhooks). */
export default function JobsPage() {
  const { t, i18n } = useTranslation();
  const [kindFilter, setKindFilter] = useState<string>("all");

  const {
    data: autoLogs,
    isLoading: l1,
    isError: e1,
    refetch: refetchLogs,
  } = useQuery({
    queryKey: ["automation-logs-all"],
    queryFn: automationsApi.allLogs,
  });
  const {
    data: syncOps,
    isLoading: l2,
    isError: e2,
    refetch: refetchSync,
  } = useQuery({
    queryKey: ["sync-operations"],
    queryFn: syncOperationsApi.list,
  });
  const {
    data: deliveries,
    isLoading: l3,
    isError: e3,
    refetch: refetchDeliveries,
  } = useQuery({
    queryKey: ["webhook-deliveries"],
    queryFn: outgoingWebhooksApi.deliveries,
  });

  const refetchAll = () => {
    void refetchLogs();
    void refetchSync();
    void refetchDeliveries();
  };

  const rows = useMemo<JobRow[]>(() => {
    const out: JobRow[] = [];
    for (const l of (Array.isArray(autoLogs) ? autoLogs : []) as Record<
      string,
      unknown
    >[]) {
      out.push({
        key: `a-${l.id}`,
        kind: "automation",
        label: t("p.admin.jobs.ruleLabel", { id: l.rule ?? "?" }),
        status: String(l.status ?? ""),
        detail:
          String(l.error_message ?? "") ||
          (l.action_result != null
            ? typeof l.action_result === "string"
              ? l.action_result
              : humanizeActionResult(
                  l.action_result as Record<string, unknown>,
                  t,
                )
            : ""),
        date: String(l.created_at ?? ""),
      });
    }
    for (const op of Array.isArray(syncOps) ? syncOps : []) {
      out.push({
        key: `s-${op.id}`,
        kind: "sync",
        label: [
          op.op_type
            ? t(`p.admin.jobs.op.${op.op_type}`, { defaultValue: op.op_type })
            : "",
          op.entity_type
            ? t(`p.admin.jobs.entity.${op.entity_type}`, {
                defaultValue: op.entity_type,
              })
            : "",
        ]
          .filter(Boolean)
          .join(" "),
        status: op.status ?? "",
        detail: op.conflict_status === "conflict" ? t("p.admin.jobs.conflict") : "",
        date: op.created_at ?? "",
      });
    }
    for (const d of (Array.isArray(deliveries) ? deliveries : []) as Record<
      string,
      unknown
    >[]) {
      const retries = Number(d.retry_count ?? 0);
      out.push({
        key: `w-${d.id}`,
        kind: "webhook",
        label: String(d.event_type || d.action || "webhook"),
        status: String(d.status ?? ""),
        detail:
          retries > 0 ? t("p.admin.jobs.retries", { n: retries }) : String(d.error || ""),
        date: String(d.created_at ?? ""),
      });
    }
    out.sort((a, b) => b.date.localeCompare(a.date));
    return out;
  }, [autoLogs, syncOps, deliveries, t]);

  const filtered =
    kindFilter === "all" ? rows : rows.filter((r) => r.kind === kindFilter);
  const loading = l1 || l2 || l3;

  return (
    <Box>
      <PageHeader
        title={t("p.admin.jobs.title")}
        description={t("p.admin.jobs.description")}
        breadcrumbs={[
          { label: t("p.admin.breadcrumb"), to: "/app/admin" },
          { label: t("p.admin.jobs.breadcrumb") },
        ]}
      />

      <ToggleButtonGroup
        size="small"
        exclusive
        value={kindFilter}
        onChange={(_, v) => v && setKindFilter(v)}
        sx={{ mb: 2 }}
      >
        <ToggleButton value="all">
          <ListChecks size={14} style={{ marginRight: 6 }} />{" "}
          {t("p.admin.jobs.filterAll", { n: rows.length })}
        </ToggleButton>
        <ToggleButton value="automation">{t("nav.automations")}</ToggleButton>
        <ToggleButton value="sync">{t("p.admin.jobs.filterSync")}</ToggleButton>
        <ToggleButton value="webhook">{t("nav.webhooks")}</ToggleButton>
      </ToggleButtonGroup>

      {(e1 || e2 || e3) && (
        <Alert
          severity="warning"
          sx={{ mb: 2 }}
          action={
            <Button size="small" onClick={refetchAll} startIcon={<RefreshCw size={14} />}>
              {t("common.retry")}
            </Button>
          }
        >
          {t("p.admin.jobs.loadError")}
        </Alert>
      )}

      {loading ? (
        <TableSkeleton rows={8} cols={5} />
      ) : filtered.length === 0 ? (
        <Paper variant="outlined">
          <EmptyState title={t("p.admin.jobs.empty")} />
        </Paper>
      ) : (
        <Paper variant="outlined" sx={{ overflowX: "auto" }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t("p.admin.jobs.colType")}</TableCell>
                <TableCell>{t("p.admin.jobs.colProcess")}</TableCell>
                <TableCell>{t("p.admin.jobs.colStatus")}</TableCell>
                <TableCell>{t("p.admin.jobs.colDetail")}</TableCell>
                <TableCell>{t("p.admin.jobs.colDate")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filtered.slice(0, 100).map((r) => (
                <TableRow key={r.key}>
                  <TableCell>
                    <Tooltip title={t(KIND_META[r.kind].label)}>
                      <Chip
                        size="small"
                        variant="outlined"
                        icon={KIND_META[r.kind].icon}
                        label={t(KIND_META[r.kind].label)}
                      />
                    </Tooltip>
                  </TableCell>
                  <TableCell>{r.label}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={
                        r.status
                          ? i18n.exists(`p.admin.jobs.status.${r.status}`)
                            ? t(`p.admin.jobs.status.${r.status}`)
                            : t("p.admin.jobs.status.unknown")
                          : "—"
                      }
                      color={STATUS_COLOR[r.status] ?? "default"}
                      variant={STATUS_COLOR[r.status] ? "filled" : "outlined"}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{
                        display: "block",
                        maxWidth: 320,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {r.detail}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">
                      {r.date ? formatDateTime(r.date) : "—"}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {filtered.length > 100 && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ p: 1.5, display: "block" }}
            >
              {t("p.admin.jobs.showingLatest", { total: filtered.length })}
            </Typography>
          )}
        </Paper>
      )}
    </Box>
  );
}
