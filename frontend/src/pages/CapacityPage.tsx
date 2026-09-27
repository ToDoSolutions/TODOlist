import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { advancedMetricsApi } from "../api/resources";
import type { CapacityEntry } from "../types";
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Chip,
  LinearProgress,
  Alert,
} from "@mui/material";

export default function CapacityPage() {
  const { t } = useTranslation();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["capacity"],
    queryFn: advancedMetricsApi.capacity,
  });

  if (isLoading) return <CircularProgress />;

  if (isError) {
    return (
      <Box maxWidth={1000} mx="auto" mt={4}>
        <Alert severity="error">{t("p.plan.capacity.loadError")}</Alert>
      </Box>
    );
  }

  const capacity = data?.capacity || [];
  const maxPoints = Math.max(...capacity.map((c: CapacityEntry) => c.total_points), 1);

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        {t("p.plan.capacity.title")}
      </Typography>
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
            <LinearProgress
              variant="determinate"
              value={(c.total_points / maxPoints) * 100}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
        ))}
      </Paper>
    </Box>
  );
}
