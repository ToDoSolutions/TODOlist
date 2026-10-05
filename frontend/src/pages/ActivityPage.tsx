import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Box,
  Typography,
  Stack,
  Paper,
  TextField,
  MenuItem,
  Chip,
  Divider,
  InputAdornment,
} from "@mui/material";
import { Search, Activity as ActivityIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { parseISO, isToday, isYesterday } from "date-fns";
import { formatDayName, formatTime } from "../lib/dates";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/states";
import { activityFeedApi, type ActivityItem } from "../api/resources";

/**
 * Centro de actividad global: feed unificado de TaskActivity + AuditLog.
 * Agrupa entradas por día y permite filtrar por tipo/acción/texto.
 */
export default function ActivityPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<"all" | "task_activity" | "audit">("all");
  const [limit, setLimit] = useState(100);

  const { data: feed } = useQuery({
    queryKey: ["activity-feed", limit],
    queryFn: () => activityFeedApi.list(limit),
  });
  const items = useMemo(() => (Array.isArray(feed) ? feed : []), [feed]);

  const filtered = useMemo(() => {
    let list = items;
    if (kind !== "all") list = list.filter((a) => a.kind === kind);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (a) =>
          a.summary.toLowerCase().includes(q) ||
          (a.actor ?? "").toLowerCase().includes(q) ||
          a.resource.toLowerCase().includes(q),
      );
    }
    return list;
  }, [items, kind, search]);

  // Agrupar por día
  const grouped = useMemo(() => {
    const g: Record<string, ActivityItem[]> = {};
    for (const a of filtered) {
      const d = parseISO(a.created_at);
      const label = isToday(d)
        ? t("p.collab.activity.today")
        : isYesterday(d)
          ? t("p.collab.activity.yesterday")
          : formatDayName(d);
      (g[label] ||= []).push(a);
    }
    return g;
  }, [filtered, t]);

  return (
    <Box>
      <PageHeader
        title={t("p.collab.activity.title")}
        description={t("p.collab.activity.desc")}
        breadcrumbs={[
          { label: t("nav.teams") },
          { label: t("p.collab.activity.title") },
        ]}
      />

      <Stack direction="row" spacing={1.5} mb={3} flexWrap="wrap" useFlexGap>
        <TextField
          size="small"
          placeholder={t("p.collab.activity.searchPlaceholder")}
          inputProps={{ "aria-label": t("p.collab.activity.searchPlaceholder") }}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ minWidth: 240 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search size={16} />
              </InputAdornment>
            ),
          }}
        />
        <TextField
          select
          size="small"
          label={t("p.collab.activity.kind")}
          value={kind}
          onChange={(e) => setKind(e.target.value as typeof kind)}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value="all">{t("p.collab.activity.all")}</MenuItem>
          <MenuItem value="task_activity">{t("p.collab.activity.taskChanges")}</MenuItem>
          <MenuItem value="audit">{t("p.collab.activity.audit")}</MenuItem>
        </TextField>
        <TextField
          select
          size="small"
          label={t("p.collab.activity.limit")}
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          sx={{ minWidth: 120 }}
        >
          {[50, 100, 200].map((n) => (
            <MenuItem key={n} value={n}>
              {t("p.collab.activity.entries", { count: n })}
            </MenuItem>
          ))}
        </TextField>
      </Stack>

      {filtered.length === 0 ? (
        <EmptyState
          title={t("p.collab.activity.emptyTitle")}
          description={t("p.collab.activity.emptyDesc")}
        />
      ) : (
        <Stack spacing={3}>
          {Object.entries(grouped).map(([day, entries]) => (
            <Box key={day}>
              <Typography variant="overline" color="text.secondary" fontWeight={700}>
                {day}
              </Typography>
              <Stack spacing={0.5} mt={0.5} divider={<Divider />}>
                {entries.map((a, i) => (
                  <Paper
                    key={i}
                    variant="outlined"
                    sx={{ p: 1.25, display: "flex", gap: 1.5, alignItems: "center" }}
                  >
                    <ActivityIcon
                      size={14}
                      color={a.kind === "audit" ? "#9c27b0" : "#1976d2"}
                    />
                    <Box flex={1} minWidth={0}>
                      <Typography variant="body2">{a.summary}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {a.actor ?? t("p.collab.activity.system")} ·{" "}
                        {a.kind === "audit"
                          ? t("p.collab.activity.auditLower")
                          : a.resource}
                      </Typography>
                    </Box>
                    <Chip
                      size="small"
                      variant="outlined"
                      label={formatTime(a.created_at)}
                      sx={{ height: 20, fontSize: 10 }}
                    />
                  </Paper>
                ))}
              </Stack>
            </Box>
          ))}
        </Stack>
      )}
    </Box>
  );
}
