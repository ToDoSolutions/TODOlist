import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Stack,
  Paper,
  TextField,
  InputAdornment,
  Chip,
  Button,
} from "@mui/material";
import { Search, Scale } from "lucide-react";
import { formatDate } from "../lib/dates";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/states";
import { meetingsApi, projectsApi, type MeetingItem } from "../api/resources";

/**
 * Registro de decisiones: consolida las decisiones tomadas en reuniones
 * en una lista cronológica consultable (fuente: Meeting.decisions).
 */
export default function DecisionsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [q, setQ] = useState("");

  const { data: meetingsData } = useQuery({
    queryKey: ["meetings"],
    queryFn: () => meetingsApi.list(),
  });
  const meetings: MeetingItem[] = useMemo(
    () => (Array.isArray(meetingsData) ? meetingsData : []),
    [meetingsData],
  );

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projectName = (id: number | null) =>
    (Array.isArray(projectsData) ? projectsData : []).find((p) => p.id === id)?.name ??
    null;

  const withDecisions = useMemo(
    () =>
      meetings
        .filter((m) => m.decisions?.trim())
        .sort((a, b) => (b.scheduled_at ?? "").localeCompare(a.scheduled_at ?? "")),
    [meetings],
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return withDecisions;
    return withDecisions.filter(
      (m) =>
        m.title.toLowerCase().includes(needle) ||
        (m.decisions ?? "").toLowerCase().includes(needle) ||
        (projectName(m.project) ?? "").toLowerCase().includes(needle),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [withDecisions, q, projectsData]);

  return (
    <Box>
      <PageHeader
        title={t("p.plan.decisions.title")}
        description={t("p.plan.decisions.desc", { count: withDecisions.length })}
        breadcrumbs={[
          { label: t("p.plan.decisions.breadcrumbKnowledge") },
          { label: t("p.plan.decisions.breadcrumb") },
        ]}
      />

      <TextField
        size="small"
        fullWidth
        placeholder={t("p.plan.decisions.searchPlaceholder")}
        inputProps={{ "aria-label": t("p.plan.decisions.searchPlaceholder") }}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        sx={{ mb: 3, maxWidth: 480 }}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <Search size={16} />
            </InputAdornment>
          ),
        }}
      />

      {filtered.length === 0 ? (
        <EmptyState
          title={t("p.plan.decisions.emptyTitle")}
          description={t("p.plan.decisions.emptyDesc")}
          icon={<Scale size={40} />}
          action={
            <Button variant="contained" onClick={() => navigate("/app/meetings")}>
              {t("p.plan.decisions.goToMeetings")}
            </Button>
          }
        />
      ) : (
        <Stack spacing={1.5}>
          {filtered.map((m) => (
            <Paper key={m.id} variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" spacing={1.5} alignItems="flex-start">
                <Scale size={18} color="#7b1fa2" style={{ marginTop: 2 }} />
                <Box flex={1} minWidth={0}>
                  <Stack
                    direction="row"
                    spacing={1}
                    alignItems="center"
                    flexWrap="wrap"
                    useFlexGap
                  >
                    <Typography variant="subtitle2" fontWeight={700}>
                      {m.title}
                    </Typography>
                    {projectName(m.project) && (
                      <Chip
                        size="small"
                        label={projectName(m.project)}
                        variant="outlined"
                      />
                    )}
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(m.scheduled_at)}
                    </Typography>
                  </Stack>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mt: 0.5, whiteSpace: "pre-line" }}
                  >
                    {m.decisions}
                  </Typography>
                </Box>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}
    </Box>
  );
}
