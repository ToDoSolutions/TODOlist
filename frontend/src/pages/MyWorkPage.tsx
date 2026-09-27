import { formatDate } from "../lib/dates";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { format, addDays, addWeeks } from "date-fns";
import { es, enUS } from "date-fns/locale";
import {
  Box,
  Typography,
  Stack,
  Chip,
  Paper,
  useTheme,
  Alert,
  Button,
  Menu,
  MenuItem,
} from "@mui/material";
import {
  AlertTriangle,
  Clock,
  Play,
  Ban,
  CalendarClock,
  CheckCircle2,
  CalendarPlus,
} from "lucide-react";
import { tasksApi, bulkOpsApi, type MyWorkTask } from "../api/resources";
import { notify } from "../notify";
import type { TaskState } from "../types";
import { TASK_STATE_I18N_KEYS } from "../i18n/batchTaskUi";
import PageHeader from "../components/ui/PageHeader";
import { PageSkeleton } from "../components/ui/skeletons";

function Section({
  title,
  icon,
  color,
  tasks,
  empty,
  action,
}: {
  title: string;
  icon: React.ReactNode;
  color: string;
  tasks: MyWorkTask[];
  empty?: string;
  action?: React.ReactNode;
}) {
  const { t: tr } = useTranslation();
  if (!tasks.length && !empty) return null;
  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1} mb={1.5}>
        <Box sx={{ color, display: "flex" }}>{icon}</Box>
        <Typography variant="subtitle1" fontWeight={700}>
          {title}
        </Typography>
        {tasks.length > 0 && (
          <Chip
            label={tasks.length}
            size="small"
            sx={{ height: 20, bgcolor: color + "1A", color }}
          />
        )}
        {tasks.length > 0 && action}
      </Stack>
      {tasks.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ pl: 4 }}>
          {empty}
        </Typography>
      ) : (
        <Stack spacing={0.5} sx={{ pl: 4 }}>
          {tasks.map((t) => (
            <Stack
              key={t.id}
              direction="row"
              alignItems="center"
              spacing={1.5}
              sx={{
                py: 0.75,
                px: 1.5,
                borderRadius: 1.5,
                "&:hover": { bgcolor: "action.hover" },
              }}
            >
              <Typography
                variant="body2"
                fontWeight={600}
                sx={{
                  flex: 1,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {t.title}
              </Typography>
              {t.blocked_by?.map((b) => (
                <Chip
                  key={b.id}
                  size="small"
                  variant="outlined"
                  color="error"
                  label={`🔒 ${b.title}`}
                />
              ))}
              {t.project && (
                <Typography variant="caption" color="text.secondary">
                  {t.project}
                </Typography>
              )}
              {t.due_date && (
                <Typography variant="caption" color="text.secondary">
                  {formatDate(t.due_date)}
                </Typography>
              )}
              <Chip
                label={tr(TASK_STATE_I18N_KEYS[t.state as TaskState])}
                size="small"
                variant="outlined"
                sx={{ height: 20 }}
              />
            </Stack>
          ))}
        </Stack>
      )}
    </Box>
  );
}

export default function MyWorkPage() {
  const theme = useTheme();
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === "en" ? enUS : es;
  const qc = useQueryClient();
  const [postponeAnchor, setPostponeAnchor] = useState<HTMLElement | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["my-work"],
    queryFn: tasksApi.myWork,
  });

  const postponeMut = useMutation({
    mutationFn: (payload: { ids: number[]; date: string }) =>
      bulkOpsApi.update(payload.ids, { due_date: payload.date }),
    onSuccess: (_r, v) => {
      notify.success(t("p.work.myWork.postponed", { count: v.ids.length }));
      setPostponeAnchor(null);
      qc.invalidateQueries({ queryKey: ["my-work"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: () => notify.error(t("p.work.myWork.postponeError")),
  });

  if (isError) {
    return <Alert severity="error">{t("p.work.myWork.loadError")}</Alert>;
  }
  if (isLoading) {
    return (
      <Box maxWidth={760} mx="auto">
        <PageSkeleton kind="list" />
      </Box>
    );
  }

  const raw = data || {
    overdue: [],
    due_today: [],
    in_progress: [],
    blocked: [],
    upcoming: [],
  };

  // Una tarea puede cumplir varios criterios a la vez (vencida + bloqueada +
  // en progreso). Cada tarea aparece solo en la sección de mayor prioridad
  // para evitar ruido y conteos inflados; los indicadores secundarios
  // (bloqueo, estado) siguen visibles en la propia fila.
  const seen = new Set<number>();
  const dedupe = (list: MyWorkTask[]) =>
    list.filter((t) => !seen.has(t.id) && (seen.add(t.id), true));
  const d = {
    overdue: dedupe(raw.overdue),
    due_today: dedupe(raw.due_today),
    blocked: dedupe(raw.blocked),
    in_progress: dedupe(raw.in_progress),
    upcoming: dedupe(raw.upcoming),
  };
  const total = d.overdue.length + d.due_today.length + d.in_progress.length;

  // Cabecera "Hoy" estilo Todoist: fecha localizada + conteo de atención.
  const todayLabel = format(
    new Date(),
    i18n.language === "en" ? "EEEE, MMMM d" : "EEEE d 'de' MMMM",
    { locale: dateLocale },
  );
  const subtitle =
    total > 0
      ? t("p.work.myWork.attentionCount", { count: total })
      : t("p.work.myWork.allUpToDate");

  return (
    <Box maxWidth={760} mx="auto">
      <PageHeader
        title={t("p.work.home.todayHeading")}
        description={`${todayLabel} · ${subtitle}`}
      />

      <Stack spacing={4}>
        <Section
          title={t("p.work.home.overdue")}
          icon={<AlertTriangle size={18} />}
          color={theme.palette.error.main}
          tasks={d.overdue}
          empty={t("p.work.myWork.overdueEmpty")}
          action={
            <>
              <Button
                size="small"
                variant="text"
                startIcon={<CalendarPlus size={14} />}
                disabled={postponeMut.isPending}
                onClick={(e) => setPostponeAnchor(e.currentTarget)}
                sx={{ ml: "auto" }}
              >
                {t("p.work.myWork.postpone")}
              </Button>
              <Menu
                anchorEl={postponeAnchor}
                open={!!postponeAnchor}
                onClose={() => setPostponeAnchor(null)}
              >
                {(
                  [
                    [t("p.work.myWork.postponeToday"), addDays(new Date(), 0)],
                    [t("p.work.myWork.postponeTomorrow"), addDays(new Date(), 1)],
                    [t("p.work.myWork.postponeWeek"), addWeeks(new Date(), 1)],
                  ] as [string, Date][]
                ).map(([label, date]) => (
                  <MenuItem
                    key={label}
                    onClick={() =>
                      postponeMut.mutate({
                        ids: d.overdue.map((task) => task.id),
                        date: format(date, "yyyy-MM-dd"),
                      })
                    }
                  >
                    {label}
                  </MenuItem>
                ))}
              </Menu>
            </>
          }
        />
        <Section
          title={t("p.work.home.today")}
          icon={<Clock size={18} />}
          color={theme.palette.warning.main}
          tasks={d.due_today}
          empty={t("p.work.myWork.todayEmpty")}
        />
        <Section
          title={t("p.work.home.blocked")}
          icon={<Ban size={18} />}
          color={theme.palette.secondary.main}
          tasks={d.blocked}
          empty={t("p.work.myWork.blockedEmpty")}
        />
        <Section
          title={t("task.state.in_progress")}
          icon={<Play size={18} />}
          color={theme.palette.info.main}
          tasks={d.in_progress}
        />
        <Section
          title={t("p.work.myWork.upcoming")}
          icon={<CalendarClock size={18} />}
          color={theme.palette.text.disabled}
          tasks={d.upcoming}
        />
        {total === 0 && d.blocked.length === 0 && (
          <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
            <CheckCircle2 size={40} style={{ color: theme.palette.success.main }} />
            <Typography variant="h6" mt={2} fontWeight={700}>
              {t("p.work.myWork.allDone")}
            </Typography>
            <Typography variant="body2" color="text.secondary" mt={0.5}>
              {t("p.work.myWork.allDoneDesc")}
            </Typography>
          </Paper>
        )}
      </Stack>
    </Box>
  );
}
