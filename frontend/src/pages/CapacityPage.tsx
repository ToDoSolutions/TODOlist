import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { advancedMetricsApi } from "../api/resources";
import type { CapacityEntry } from "../types";
import PageHeader from "../components/ui/PageHeader";
import { PageSkeleton } from "../components/ui/skeletons";
import { ErrorState } from "../components/ui/states";
import {
  Box,
  Typography,
  Paper,
  Chip,
  LinearProgress,
  Alert,
  Tooltip,
} from "@mui/material";

export default function CapacityPage() {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["capacity"],
    queryFn: advancedMetricsApi.capacity,
  });

  if (isLoading) return <PageSkeleton kind="list" />;

  if (isError) {
    return (
      <Box maxWidth={1000} mx="auto" mt={4}>
        <ErrorState title={t("p.plan.capacity.loadError")} onRetry={() => void refetch()} />
      </Box>
    );
  }

  const capacity = data?.capacity || [];
  const maxPoints = Math.max(...capacity.map((c: CapacityEntry) => c.total_points), 1);

  return (
    <Box>
      <PageHeader title={t("p.plan.capacity.title")} />
      <Paper sx={{ p: 2 }}>
        {capacity.length === 0 && (
          <Typography color="textSecondary">{t("p.plan.capacity.noData")}</Typography>
        )}
        {capacity.map((c: CapacityEntry, i: number) => (
          <Box key={i} sx={{ mb: 2 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
              <Box
                sx={{
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  bgcolor: c.project_color,
                }}
              />
              <Typography sx={{ flex: 1 }}>{c.project}</Typography>
              <Chip
                label={t("p.plan.capacity.pointsChip", { count: c.total_points })}
                size="small"
                color="primary"
              />
              <Chip
                label={t("p.plan.capacity.openChip", { count: c.open_tasks })}
                size="small"
                variant="outlined"
              />
              {c.in_progress > 0 && (
                <Chip
                  label={t("p.plan.capacity.inProgressChip", { count: c.in_progress })}
                  size="small"
                  color="info"
                />
              )}
              {c.blocked > 0 && (
                <Chip
                  label={t("p.plan.capacity.blockedChip", { count: c.blocked })}
                  size="small"
                  color="error"
                />
              )}
            </Box>
            <Tooltip
              title={t("p.plan.capacity.barTip", {
                pct: Math.round((c.total_points / maxPoints) * 100),
              })}
            >
              <Box>
                <LinearProgress
                  variant="determinate"
                  value={(c.total_points / maxPoints) * 100}
                  sx={{ height: 8, borderRadius: 4 }}
                />
              </Box>
            </Tooltip>
          </Box>
        ))}
      </Paper>
    </Box>
  );
}
