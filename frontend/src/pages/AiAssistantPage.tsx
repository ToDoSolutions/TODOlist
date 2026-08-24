import { useQuery } from "@tanstack/react-query";
import { aiApi } from "../api/resources";
import { Box, Typography, CircularProgress, Paper, Chip, Alert, Button } from "@mui/material";
import { Lightbulb, AlertTriangle, TrendingUp } from "lucide-react";

export default function AiAssistantPage() {
  const { data: blockersData, isLoading: blockersLoading } = useQuery({
    queryKey: ["ai-blockers"],
    queryFn: aiApi.detectBlockers,
  });

  const { data: suggestionsData } = useQuery({
    queryKey: ["ai-suggestions"],
    queryFn: aiApi.suggestions,
  });

  const blockers = blockersData?.blockers || [];
  const suggestions = suggestionsData?.results || suggestionsData || [];

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        <Lightbulb size={24} style={{ verticalAlign: "middle", marginRight: 8 }} />
        AI Assistant
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" gutterBottom>
          <AlertTriangle size={20} style={{ verticalAlign: "middle", marginRight: 8 }} />
          Bloqueos detectados
        </Typography>
        {blockersLoading && <CircularProgress size={20} />}
        {blockers.length === 0 && !blockersLoading && (
          <Alert severity="success">No se detectaron bloqueos</Alert>
        )}
        {blockers.map((b: any, i: number) => (
          <Box key={i} sx={{ mb: 1, display: "flex", gap: 1, alignItems: "center" }}>
            <Chip
              label={b.severity}
              size="small"
              color={b.severity === "high" ? "error" : b.severity === "medium" ? "warning" : "default"}
            />
            <Typography variant="body2">{b.message}</Typography>
          </Box>
        ))}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          <TrendingUp size={20} style={{ verticalAlign: "middle", marginRight: 8 }} />
          Sugerencias recientes
        </Typography>
        {suggestions.length === 0 && <Typography color="textSecondary">Sin sugerencias aún</Typography>}
        {suggestions.map((s: any) => (
          <Box key={s.id} sx={{ mb: 1, pb: 1, borderBottom: "1px solid #eee" }}>
            <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
              <Chip label={s.suggestion_type} size="small" color="primary" />
              <Typography variant="caption">
                Confianza: {Math.round((s.confidence || 0) * 100)}%
              </Typography>
            </Box>
          </Box>
        ))}
      </Paper>
    </Box>
  );
}
