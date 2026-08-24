import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { aiApi } from "../api/resources";
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Chip,
  Alert,
  Button,
  TextField,
  Stack,
} from "@mui/material";
import {
  Lightbulb,
  AlertTriangle,
  TrendingUp,
  Sparkles,
  FileText,
} from "lucide-react";
import { notify } from "../notify";

interface PriorityResult {
  task_id: number;
  suggested_priority: number;
  confidence: number;
  reasoning: string;
}

interface StoryPointsResult {
  task_id: number;
  suggested_points: number;
  confidence: number;
  reasoning: string;
}

interface DescriptionResult {
  task_id: number;
  improved_description: string;
  suggestions: string[];
}

export default function AiAssistantPage() {
  const [taskId, setTaskId] = useState("");
  const [priorityResult, setPriorityResult] = useState<PriorityResult | null>(null);
  const [storyPointsResult, setStoryPointsResult] = useState<StoryPointsResult | null>(null);
  const [descriptionResult, setDescriptionResult] = useState<DescriptionResult | null>(null);

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

  const priorityMutation = useMutation({
    mutationFn: (id: number) => aiApi.estimatePriority(id),
    onSuccess: (data: PriorityResult) => setPriorityResult(data),
    onError: (err: any) => {
      notify.error(err?.response?.data?.detail || "Error al estimar prioridad");
    },
  });

  const storyPointsMutation = useMutation({
    mutationFn: (id: number) => aiApi.estimateStoryPoints(id),
    onSuccess: (data: StoryPointsResult) => setStoryPointsResult(data),
    onError: (err: any) => {
      notify.error(err?.response?.data?.detail || "Error al estimar story points");
    },
  });

  const descriptionMutation = useMutation({
    mutationFn: (id: number) => aiApi.improveDescription(id),
    onSuccess: (data: DescriptionResult) => setDescriptionResult(data),
    onError: (err: any) => {
      notify.error(err?.response?.data?.detail || "Error al mejorar descripción");
    },
  });

  const handlePriority = () => {
    const id = parseInt(taskId, 10);
    if (!id) {
      notify.warning("Ingresa un ID de tarea válido");
      return;
    }
    setPriorityResult(null);
    priorityMutation.mutate(id);
  };

  const handleStoryPoints = () => {
    const id = parseInt(taskId, 10);
    if (!id) {
      notify.warning("Ingresa un ID de tarea válido");
      return;
    }
    setStoryPointsResult(null);
    storyPointsMutation.mutate(id);
  };

  const handleImproveDescription = () => {
    const id = parseInt(taskId, 10);
    if (!id) {
      notify.warning("Ingresa un ID de tarea válido");
      return;
    }
    setDescriptionResult(null);
    descriptionMutation.mutate(id);
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        <Lightbulb size={24} style={{ verticalAlign: "middle", marginRight: 8 }} />
        Asistente Inteligente
      </Typography>

      {/* Task Analysis Section */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" gutterBottom>
          <Sparkles size={20} style={{ verticalAlign: "middle", marginRight: 8 }} />
          Análisis de tarea
        </Typography>
        <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
          Ingresa el ID de una tarea y usa las sugerencias automáticas para analizarla.
        </Typography>
        <Stack direction="row" spacing={2} sx={{ mb: 2, alignItems: "center" }}>
          <TextField
            label="ID de tarea"
            value={taskId}
            onChange={(e) => setTaskId(e.target.value)}
            size="small"
            type="number"
            sx={{ width: 150 }}
          />
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Button
              variant="contained"
              size="small"
              startIcon={
                priorityMutation.isPending ? (
                  <CircularProgress size={16} color="inherit" />
                ) : (
                  <TrendingUp size={16} />
                )
              }
              onClick={handlePriority}
              disabled={priorityMutation.isPending || !taskId}
            >
              Estimar prioridad
            </Button>
            <Button
              variant="contained"
              size="small"
              startIcon={
                storyPointsMutation.isPending ? (
                  <CircularProgress size={16} color="inherit" />
                ) : (
                  <Sparkles size={16} />
                )
              }
              onClick={handleStoryPoints}
              disabled={storyPointsMutation.isPending || !taskId}
            >
              Estimar story points
            </Button>
            <Button
              variant="contained"
              size="small"
              startIcon={
                descriptionMutation.isPending ? (
                  <CircularProgress size={16} color="inherit" />
                ) : (
                  <FileText size={16} />
                )
              }
              onClick={handleImproveDescription}
              disabled={descriptionMutation.isPending || !taskId}
            >
              Mejorar descripción
            </Button>
          </Stack>
        </Stack>

        {/* Results */}
        <Stack spacing={2}>
          {priorityResult && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
                <TrendingUp size={18} />
                <Typography variant="subtitle2">Prioridad estimada</Typography>
              </Box>
              <Stack direction="row" spacing={1} sx={{ mb: 1, alignItems: "center" }}>
                <Chip
                  label={`Prioridad: ${priorityResult.suggested_priority}`}
                  color="primary"
                  size="small"
                />
                <Chip
                  label={`Confianza: ${Math.round((priorityResult.confidence || 0) * 100)}%`}
                  size="small"
                  variant="outlined"
                />
              </Stack>
              {priorityResult.reasoning && (
                <Typography variant="body2" color="textSecondary">
                  {priorityResult.reasoning}
                </Typography>
              )}
            </Paper>
          )}

          {storyPointsResult && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
                <Sparkles size={18} />
                <Typography variant="subtitle2">Story points estimados</Typography>
              </Box>
              <Stack direction="row" spacing={1} sx={{ mb: 1, alignItems: "center" }}>
                <Chip
                  label={`Puntos: ${storyPointsResult.suggested_points}`}
                  color="primary"
                  size="small"
                />
                <Chip
                  label={`Confianza: ${Math.round((storyPointsResult.confidence || 0) * 100)}%`}
                  size="small"
                  variant="outlined"
                />
              </Stack>
              {storyPointsResult.reasoning && (
                <Typography variant="body2" color="textSecondary">
                  {storyPointsResult.reasoning}
                </Typography>
              )}
            </Paper>
          )}

          {descriptionResult && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
                <FileText size={18} />
                <Typography variant="subtitle2">Descripción mejorada</Typography>
              </Box>
              <Typography variant="body2" sx={{ mb: 1, whiteSpace: "pre-wrap" }}>
                {descriptionResult.improved_description}
              </Typography>
              {descriptionResult.suggestions?.length > 0 && (
                <Box>
                  <Typography variant="caption" color="textSecondary">
                    Sugerencias:
                  </Typography>
                  <Stack spacing={0.5} sx={{ mt: 0.5 }}>
                    {descriptionResult.suggestions.map((s, i) => (
                      <Typography key={i} variant="body2" color="textSecondary">
                        • {s}
                      </Typography>
                    ))}
                  </Stack>
                </Box>
              )}
            </Paper>
          )}
        </Stack>
      </Paper>

      {/* Detected Blockers */}
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

      {/* Recent Suggestions */}
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
