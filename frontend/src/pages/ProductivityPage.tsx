// ProductivityPage — métricas de productividad (GET /tasks/productivity/):
// racha de días consecutivos completando, total del período, media diaria,
// mejor día y un histograma de completadas por día (recharts).
import { useMemo, useState } from "react";
import {
  Box,
  Paper,
  Stack,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  CircularProgress,
  Alert,
} from "@mui/material";
import { Flame, CheckCircle2, TrendingUp, Trophy } from "lucide-react";
import { format, parseISO, subDays } from "date-fns";
import { es, enUS } from "date-fns/locale";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as ChartTooltip,
  CartesianGrid,
} from "recharts";
import { useTheme } from "@mui/material";
import { taskX2Api } from "../api/featTask2";

const RANGES = [7, 30, 90] as const;

export default function ProductivityPage() {
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === "en" ? enUS : es;
  const theme = useTheme();
  const [days, setDays] = useState<number>(30);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["task-productivity", days],
    queryFn: () => taskX2Api.productivity(days),
  });

  // Rellena los días sin completadas con count=0 para un histograma
  // continuo (el endpoint solo devuelve días con actividad).
  const chartData = useMemo(() => {
    const byDay = new Map((data?.daily ?? []).map((d) => [d.date, d.count]));
    const today = new Date();
    const arr: { label: string; date: string; count: number }[] = [];
    for (let i = days - 1; i >= 0; i--) {
      const d = subDays(today, i);
      const key = format(d, "yyyy-MM-dd");
      arr.push({
        date: key,
        label: format(d, "d MMM", { locale: dateLocale }),
        count: byDay.get(key) ?? 0,
      });
    }
    return arr;
  }, [data, days, dateLocale]);

  const bestDay = data?.best_day
    ? format(parseISO(data.best_day), "d MMM yyyy", { locale: dateLocale })
    : t("p.taskx.prod.noBestDay");

  const stats = [
    {
      icon: <Flame size={18} />,
      label: t("p.taskx.prod.streak"),
      value: t("p.taskx.prod.streakDays", { count: data?.streak ?? 0 }),
      color: "warning.main",
    },
    {
      icon: <CheckCircle2 size={18} />,
      label: t("p.taskx.prod.total"),
      value: String(data?.total ?? 0),
      color: "success.main",
    },
    {
      icon: <TrendingUp size={18} />,
      label: t("p.taskx.prod.avgPerDay"),
      value: (data?.avg_per_day ?? 0).toFixed(1),
      color: "info.main",
    },
    {
      icon: <Trophy size={18} />,
      label: t("p.taskx.prod.bestDay"),
      value: bestDay,
      color: "primary.main",
    },
  ];

  return (
    <Box sx={{ maxWidth: 960, mx: "auto" }}>
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        mb={3}
        flexWrap="wrap"
        useFlexGap
        spacing={1}
      >
        <Typography variant="h5" fontWeight={700}>
          {t("p.taskx.prod.title")}
        </Typography>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={days}
          onChange={(_, v) => v && setDays(v)}
          aria-label={t("p.taskx.prod.title")}
        >
          {RANGES.map((r) => (
            <ToggleButton key={r} value={r}>
              {t(`p.taskx.prod.range${r}`)}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Stack>

      {isLoading ? (
        <Stack alignItems="center" py={6}>
          <CircularProgress />
        </Stack>
      ) : isError ? (
        <Alert severity="error">{t("p.taskx.prod.error")}</Alert>
      ) : (
        <>
          {/* Tarjetas de métricas */}
          <Stack direction="row" spacing={2} mb={3} flexWrap="wrap" useFlexGap>
            {stats.map((s) => (
              <Paper
                key={s.label}
                variant="outlined"
                sx={{ p: 2, flex: "1 1 160px", minWidth: 150 }}
              >
                <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
                  <Box sx={{ color: s.color, display: "flex" }}>{s.icon}</Box>
                  <Typography variant="caption" color="text.secondary">
                    {s.label}
                  </Typography>
                </Stack>
                <Typography variant="h6" fontWeight={700}>
                  {s.value}
                </Typography>
              </Paper>
            ))}
          </Stack>

          {/* Histograma de completadas por día */}
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle2" fontWeight={600} mb={2}>
              {t("p.taskx.prod.dailyChart")}
            </Typography>
            {!data?.total ? (
              <Alert severity="info">{t("p.taskx.prod.empty")}</Alert>
            ) : (
              <Box sx={{ width: "100%", height: 300 }}>
                <ResponsiveContainer>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="label"
                      tick={{ fontSize: 11 }}
                      interval="preserveStartEnd"
                      minTickGap={20}
                    />
                    <YAxis allowDecimals={false} width={30} tick={{ fontSize: 11 }} />
                    <ChartTooltip
                      formatter={(value) => [
                        t("p.taskx.prod.completedOther", {
                          count: Number(value),
                        }),
                        t("p.taskx.prod.total"),
                      ]}
                      labelFormatter={(_l, payload) =>
                        (payload?.[0]?.payload as { date?: string } | undefined)?.date ??
                        String(_l)
                      }
                    />
                    <Bar
                      dataKey="count"
                      fill={theme.palette.primary.main}
                      radius={[3, 3, 0, 0]}
                      maxBarSize={28}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            )}
          </Paper>
        </>
      )}
    </Box>
  );
}
