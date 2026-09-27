import { Link as RouterLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Box,
  Card,
  CardContent,
  IconButton,
  LinearProgress,
  Stack,
  Typography,
} from "@mui/material";
import { CheckCircle2, Circle, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { projectsApi, tagsApi, tasksApi } from "../api/resources";
import { useUiStore } from "../store/uiStore";

/**
 * Checklist de primeros pasos (estilo Todoist/Asana) en el dashboard.
 *
 * - Pasos 1–3 se derivan de datos reales usando las mismas queryKeys que el
 *   resto de la app → la caché de TanStack Query se comparte y no hay
 *   peticiones extra cuando el usuario ya visitó otras páginas.
 * - Pasos 4–5 son flags persistidos en uiStore (`onboarding.*`): los marcan
 *   AppLayout (paleta Ctrl+K) y TasksPage (vista kanban) vía setters.
 *
 * La tarjeta se oculta al completar los 5 pasos o al descartarla (X).
 */
export default function OnboardingChecklist() {
  const { t } = useTranslation();
  const onboarding = useUiStore((s) => s.onboarding);
  const dismissOnboarding = useUiStore((s) => s.dismissOnboarding);

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const { data: tags } = useQuery({ queryKey: ["tags"], queryFn: tagsApi.list });
  // Misma queryKey que DashboardPage → cero peticiones extra.
  const { data: dashboard } = useQuery({
    queryKey: ["metrics-dashboard"],
    queryFn: tasksApi.metricsDashboard,
  });

  const taskCount = dashboard?.by_state
    ? Object.values(dashboard.by_state).reduce<number>((sum, v) => sum + Number(v), 0)
    : Number(dashboard?.open ?? 0) + Number(dashboard?.completed ?? 0);

  const steps = [
    {
      label: t("p.misc.onboarding.step.project"),
      done: Array.isArray(projects) && projects.length > 0,
      to: "/app/projects" as string | undefined,
    },
    {
      label: t("p.misc.onboarding.step.task"),
      done: taskCount > 0,
      to: "/app/tasks",
    },
    {
      label: t("p.misc.onboarding.step.tag"),
      done: Array.isArray(tags) && tags.length > 0,
      to: "/app/tags",
    },
    {
      label: t("p.misc.onboarding.step.palette"),
      done: onboarding.usedPalette,
      to: undefined,
    },
    {
      label: t("p.misc.onboarding.step.kanban"),
      done: onboarding.visitedKanban,
      to: "/app/tasks?view=kanban",
    },
  ];
  const doneCount = steps.filter((s) => s.done).length;

  if (onboarding.dismissed || doneCount === steps.length) return null;

  return (
    <Card variant="outlined" sx={{ mb: 3 }}>
      <CardContent sx={{ py: 2, "&:last-child": { pb: 2 } }}>
        <Stack direction="row" alignItems="center" spacing={1} mb={1}>
          <Typography variant="subtitle1" fontWeight={700} sx={{ flex: 1 }}>
            {t("p.misc.onboarding.title", {
              done: doneCount,
              total: steps.length,
            })}
          </Typography>
          <IconButton
            size="small"
            aria-label={t("p.misc.onboarding.dismiss")}
            onClick={dismissOnboarding}
          >
            <X size={16} />
          </IconButton>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={(doneCount / steps.length) * 100}
          sx={{ height: 6, mb: 1.5 }}
          aria-label={t("p.misc.onboarding.progressAria")}
        />
        <Stack spacing={0.5}>
          {steps.map((step) => (
            <Stack key={step.label} direction="row" alignItems="center" spacing={1}>
              <Box
                sx={{
                  display: "flex",
                  color: step.done ? "success.main" : "text.disabled",
                }}
              >
                {step.done ? <CheckCircle2 size={18} /> : <Circle size={18} />}
              </Box>
              <Typography
                variant="body2"
                {...(step.to ? { component: RouterLink, to: step.to } : {})}
                sx={{
                  color: step.done ? "text.secondary" : "text.primary",
                  textDecoration: step.done ? "line-through" : "none",
                  ...(step.to && {
                    "&:hover": {
                      color: "primary.main",
                      textDecoration: "underline",
                    },
                  }),
                }}
              >
                {step.label}
              </Typography>
            </Stack>
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}
