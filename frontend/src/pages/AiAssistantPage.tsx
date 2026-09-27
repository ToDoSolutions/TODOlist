import { formatDateTime } from "../lib/dates";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { aiApi, type ApiError } from "../api/resources";
import type { AiBlocker, AiSuggestion } from "../types";
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
  Card,
  CardContent,
  IconButton,
  Tooltip,
} from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import {
  Lightbulb,
  AlertTriangle,
  TrendingUp,
  Sparkles,
  FileText,
  Check,
  X,
  Zap,
} from "lucide-react";
import { notify } from "../notify";
import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [taskId, setTaskId] = useState("");
  const [priorityResult, setPriorityResult] = useState<PriorityResult | null>(null);
  const [storyPointsResult, setStoryPointsResult] = useState<StoryPointsResult | null>(
    null,
  );
  const [descriptionResult, setDescriptionResult] = useState<DescriptionResult | null>(
    null,
  );

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
    onError: (err: ApiError) => {
      notify.error(err?.response?.data?.detail || t("p.shell.ai.errorEstimatePriority"));
    },
  });

  const storyPointsMutation = useMutation({
    mutationFn: (id: number) => aiApi.estimateStoryPoints(id),
    onSuccess: (data: StoryPointsResult) => setStoryPointsResult(data),
    onError: (err: ApiError) => {
      notify.error(err?.response?.data?.detail || t("p.shell.ai.errorEstimatePoints"));
    },
  });

  const descriptionMutation = useMutation({
    mutationFn: (id: number) => aiApi.improveDescription(id),
    onSuccess: (data: DescriptionResult) => setDescriptionResult(data),
    onError: (err: ApiError) => {
      notify.error(
        err?.response?.data?.detail || t("p.shell.ai.errorImproveDescription"),
      );
    },
  });

  const suggestionActionMut = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "accept" | "reject" | "apply" }) =>
      aiApi.suggestionAction(id, action),
    onSuccess: (_data, { action }) => {
      notify.success(
        action === "apply"
          ? t("p.shell.ai.suggestionApplied")
          : action === "accept"
            ? t("p.shell.ai.suggestionAccepted")
            : t("p.shell.ai.suggestionRejected"),
      );
      qc.invalidateQueries({ queryKey: ["ai-suggestions"] });
    },
    onError: (err: ApiError) =>
      notify.error(err?.response?.data?.error || t("p.shell.ai.errorProcessSuggestion")),
  });

  const handlePriority = () => {
    const id = parseInt(taskId, 10);
    if (!id) {
      notify.warning(t("p.shell.ai.invalidTaskId"));
      return;
    }
    setPriorityResult(null);
    priorityMutation.mutate(id);
  };

  const handleStoryPoints = () => {
    const id = parseInt(taskId, 10);
    if (!id) {
      notify.warning(t("p.shell.ai.invalidTaskId"));
      return;
    }
    setStoryPointsResult(null);
    storyPointsMutation.mutate(id);
  };

  const handleImproveDescription = () => {
    const id = parseInt(taskId, 10);
    if (!id) {
      notify.warning(t("p.shell.ai.invalidTaskId"));
      return;
    }
    setDescriptionResult(null);
    descriptionMutation.mutate(id);
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        <Lightbulb size={24} style={{ verticalAlign: "middle", marginRight: 8 }} />
        {t("p.shell.aiAssistant")}
      </Typography>

      {/* Task Analysis Section */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" gutterBottom>
          <Sparkles size={20} style={{ verticalAlign: "middle", marginRight: 8 }} />
          {t("p.shell.ai.analysisTitle")}
        </Typography>
        <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
          {t("p.shell.ai.analysisDesc")}
        </Typography>
        <Stack direction="row" spacing={2} sx={{ mb: 2, alignItems: "center" }}>
          <TextField
            label={t("p.shell.ai.taskIdLabel")}
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
              {t("p.shell.ai.estimatePriority")}
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
              {t("p.shell.ai.estimatePoints")}
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
              {t("p.shell.ai.improveDescription")}
            </Button>
          </Stack>
        </Stack>

        {/* Results */}
        <Stack spacing={2}>
          {priorityResult && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
                <TrendingUp size={18} />
                <Typography variant="subtitle2">
                  {t("p.shell.ai.estimatedPriority")}
                </Typography>
              </Box>
              <Stack direction="row" spacing={1} sx={{ mb: 1, alignItems: "center" }}>
                <Chip
                  label={t("p.shell.ai.priorityValue", {
                    value: priorityResult.suggested_priority,
                  })}
                  color="primary"
                  size="small"
                />
                <Chip
                  label={t("p.shell.ai.confidenceValue", {
                    value: Math.round((priorityResult.confidence || 0) * 100),
                  })}
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
                <Typography variant="subtitle2">
                  {t("p.shell.ai.estimatedPoints")}
                </Typography>
              </Box>
              <Stack direction="row" spacing={1} sx={{ mb: 1, alignItems: "center" }}>
                <Chip
                  label={t("p.shell.ai.pointsValue", {
                    value: storyPointsResult.suggested_points,
                  })}
                  color="primary"
                  size="small"
                />
                <Chip
                  label={t("p.shell.ai.confidenceValue", {
                    value: Math.round((storyPointsResult.confidence || 0) * 100),
                  })}
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
                <Typography variant="subtitle2">
                  {t("p.shell.ai.improvedDescription")}
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ mb: 1, whiteSpace: "pre-wrap" }}>
                {descriptionResult.improved_description}
              </Typography>
              {descriptionResult.suggestions?.length > 0 && (
                <Box>
                  <Typography variant="caption" color="textSecondary">
                    {t("p.shell.ai.suggestionsLabel")}
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
          {t("p.shell.ai.blockersTitle")}
        </Typography>
        {blockersLoading && <CircularProgress size={20} />}
        {blockers.length === 0 && !blockersLoading && (
          <Alert severity="success">{t("p.shell.ai.noBlockers")}</Alert>
        )}
        {blockers.map((b: AiBlocker, i: number) => (
          <Box key={i} sx={{ mb: 1, display: "flex", gap: 1, alignItems: "center" }}>
            <Chip
              label={b.severity}
              size="small"
              color={
                b.severity === "high"
                  ? "error"
                  : b.severity === "medium"
                    ? "warning"
                    : "default"
              }
            />
            <Typography variant="body2">{b.message}</Typography>
          </Box>
        ))}
      </Paper>

      {/* Recent Suggestions */}
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          <TrendingUp size={20} style={{ verticalAlign: "middle", marginRight: 8 }} />
          {t("p.shell.ai.recentSuggestions")}
        </Typography>
        {suggestions.length === 0 && (
          <Typography color="textSecondary">{t("p.shell.ai.noSuggestions")}</Typography>
        )}
        {suggestions.map((s: AiSuggestion) => (
          <Box key={s.id} sx={{ mb: 1, pb: 1, borderBottom: "1px solid #eee" }}>
            <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
              <Chip label={s.suggestion_type} size="small" color="primary" />
              <Typography variant="caption">
                {t("p.shell.ai.confidenceValue", {
                  value: Math.round((s.confidence || 0) * 100),
                })}
              </Typography>
            </Box>
          </Box>
        ))}
      </Paper>

      {/* Previous Suggestions History */}
      <Typography variant="h6" sx={{ mt: 3, mb: 1 }}>
        {t("p.shell.ai.previousSuggestions")}
      </Typography>
      {suggestions.length === 0 && (
        <Typography color="textSecondary">
          {t("p.shell.ai.noPreviousSuggestions")}
        </Typography>
      )}
      <Stack spacing={2}>
        {suggestions.map((s: AiSuggestion) => {
          const confidence = s.confidence || 0;
          const confidenceColor =
            confidence > 0.8 ? "success" : confidence > 0.6 ? "warning" : "error";
          const output = s.output_data || {};
          const mainText = String(output.reason || output.summary || "");
          const action =
            output.suggested_action || output.suggested_priority
              ? output.suggested_action
                ? t("p.shell.ai.actionValue", { value: output.suggested_action })
                : t("p.shell.ai.suggestedPriorityValue", {
                    value: output.suggested_priority,
                  })
              : null;
          const created = s.created_at ? formatDateTime(s.created_at) : null;
          return (
            <Card key={s.id} variant="outlined">
              <CardContent>
                <Stack
                  direction="row"
                  spacing={1}
                  useFlexGap
                  sx={{ mb: 1, alignItems: "center", flexWrap: "wrap" }}
                >
                  <Chip label={s.suggestion_type} size="small" color="primary" />
                  <Chip
                    label={t("p.shell.ai.confidenceValue", {
                      value: Math.round(confidence * 100),
                    })}
                    size="small"
                    color={confidenceColor}
                    variant="outlined"
                  />
                  {s.task && (
                    <Chip
                      label={t("p.shell.ai.taskNumber", {
                        id: typeof s.task === "object" ? s.task.id : s.task,
                      })}
                      size="small"
                      variant="outlined"
                      component={RouterLink}
                      to="/app"
                      clickable
                    />
                  )}
                </Stack>
                {mainText && (
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    {mainText}
                  </Typography>
                )}
                {action && (
                  <Typography variant="body2" color="textSecondary" sx={{ mb: 1 }}>
                    {action}
                  </Typography>
                )}
                {created && (
                  <Typography variant="caption" color="textSecondary">
                    {created}
                  </Typography>
                )}
                {s.status === "pending" && s.task && (
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    {/* description_improvement es orientativa (consejos de
                        redacción): no hay nada que aplicar automáticamente */}
                    {s.suggestion_type !== "description_improvement" && (
                      <Tooltip title={t("p.shell.ai.applyToTask")}>
                        <Button
                          size="small"
                          variant="contained"
                          color="success"
                          startIcon={<Zap size={14} />}
                          disabled={suggestionActionMut.isPending}
                          onClick={() =>
                            suggestionActionMut.mutate({ id: s.id, action: "apply" })
                          }
                        >
                          {t("p.shell.ai.apply")}
                        </Button>
                      </Tooltip>
                    )}
                    <Tooltip title={t("p.shell.ai.accept")}>
                      <IconButton
                        size="small"
                        color="primary"
                        disabled={suggestionActionMut.isPending}
                        onClick={() =>
                          suggestionActionMut.mutate({ id: s.id, action: "accept" })
                        }
                      >
                        <Check size={16} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t("p.shell.ai.reject")}>
                      <IconButton
                        size="small"
                        color="error"
                        disabled={suggestionActionMut.isPending}
                        onClick={() =>
                          suggestionActionMut.mutate({ id: s.id, action: "reject" })
                        }
                      >
                        <X size={16} />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                )}
                {s.status !== "pending" && (
                  <Chip
                    label={s.status}
                    size="small"
                    color={
                      s.status === "applied"
                        ? "success"
                        : s.status === "accepted"
                          ? "primary"
                          : "default"
                    }
                    sx={{ mt: 1 }}
                  />
                )}
              </CardContent>
            </Card>
          );
        })}
      </Stack>
    </Box>
  );
}
