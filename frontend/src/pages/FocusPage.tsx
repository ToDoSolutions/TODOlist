// FocusPage — temporizador de enfoque tipo Pomodoro (TickTick-style).
// Duraciones persistidas en localStorage; las sesiones completadas de
// trabajo también se guardan localmente ({date, taskId?, minutes}) para
// mostrar los pomodoros y minutos de enfoque de hoy. Es solo informativo:
// no crea TimeEntry en el backend.
import { useCallback, useEffect, useState } from "react";
import {
  Box,
  Paper,
  Stack,
  Typography,
  Button,
  TextField,
  Autocomplete,
  ToggleButton,
  ToggleButtonGroup,
  CircularProgress,
  Tooltip,
  Chip,
} from "@mui/material";
import {
  Play,
  Pause,
  RotateCcw,
  SkipForward,
  Flame,
  Clock,
  CheckCircle2,
} from "lucide-react";
import { format } from "date-fns";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { tasksApi } from "../api/resources";
import type { Task } from "../types";
import { notify } from "../notify";

type FocusMode = "work" | "break";

interface FocusSession {
  /** "YYYY-MM-DD" */
  date: string;
  taskId?: number;
  minutes: number;
}

const LS_WORK = "focus.workMin";
const LS_BREAK = "focus.breakMin";
const LS_SESSIONS = "focus.sessions";

const DEFAULT_WORK = 25;
const DEFAULT_BREAK = 5;

const DONE_STATES = ["completed", "cancelled", "archived"];

function loadInt(key: string, def: number): number {
  const v = parseInt(localStorage.getItem(key) || "", 10);
  return Number.isFinite(v) && v >= 1 && v <= 180 ? v : def;
}

function loadSessions(): FocusSession[] {
  try {
    const raw = JSON.parse(localStorage.getItem(LS_SESSIONS) || "[]");
    return Array.isArray(raw) ? (raw as FocusSession[]) : [];
  } catch {
    return [];
  }
}

function saveSessions(s: FocusSession[]) {
  try {
    localStorage.setItem(LS_SESSIONS, JSON.stringify(s));
  } catch {
    // storage lleno/deshabilitado: las sesiones de hoy simplemente no persisten
  }
}

const fmt = (totalSec: number): string => {
  const s = Math.max(0, totalSec);
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${mm}:${ss}`;
};

export default function FocusPage() {
  const { t } = useTranslation();

  const [workMin, setWorkMin] = useState(() => loadInt(LS_WORK, DEFAULT_WORK));
  const [breakMin, setBreakMin] = useState(() => loadInt(LS_BREAK, DEFAULT_BREAK));
  const [mode, setMode] = useState<FocusMode>("work");
  const [running, setRunning] = useState(false);
  // Cuenta atrás por timestamp: `endAt` es el instante de fin; así el
  // temporizador no deriva con pestañas en segundo plano.
  const [endAt, setEndAt] = useState<number | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(() => workMin * 60);
  const [cycleCount, setCycleCount] = useState(0);
  const [sessions, setSessions] = useState<FocusSession[]>(loadSessions);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  const durationFor = useCallback(
    (m: FocusMode) => (m === "work" ? workMin : breakMin) * 60,
    [workMin, breakMin],
  );

  // Tareas abiertas para el selector (misma lista /tasks/, filtrada aquí).
  const { data: allTasks = [] } = useQuery({
    queryKey: ["tasks", "focus-open"],
    queryFn: () => tasksApi.list(),
  });
  const openTasks = allTasks.filter((tk) => !DONE_STATES.includes(tk.state));

  // Al llegar a 0: work → registra sesión y auto-arranca el descanso;
  // break → vuelve a trabajo en pausa esperando al usuario.
  // Se llama desde el callback del intervalo (no desde el cuerpo del
  // effect): los setState dentro son válidos según react-hooks.
  const complete = useCallback(() => {
    if (mode === "work") {
      const rec: FocusSession = {
        date: format(new Date(), "yyyy-MM-dd"),
        minutes: workMin,
      };
      if (selectedTask) rec.taskId = selectedTask.id;
      setSessions((prev) => {
        const next = [...prev, rec];
        saveSessions(next);
        return next;
      });
      setCycleCount((c) => c + 1);
      notify.success(t("p.taskx.focus.workDone"));
      setMode("break");
      setSecondsLeft(breakMin * 60);
      setEndAt(Date.now() + breakMin * 60_000);
      setRunning(true);
    } else {
      notify.info(t("p.taskx.focus.breakDone"));
      setMode("work");
      setSecondsLeft(workMin * 60);
      setEndAt(null);
      setRunning(false);
    }
  }, [mode, workMin, breakMin, selectedTask, t]);

  // Tick (250 ms para refresco fino; el remaining real sale de endAt).
  useEffect(() => {
    if (!running || endAt === null) return;
    const id = setInterval(() => {
      const left = Math.round((endAt - Date.now()) / 1000);
      if (left <= 0) {
        // Parar ya evita un segundo tick con endAt obsoleto (doble complete).
        clearInterval(id);
        complete();
      } else {
        setSecondsLeft(left);
      }
    }, 250);
    return () => clearInterval(id);
  }, [running, endAt, complete]);

  const toggle = useCallback(() => {
    if (running) {
      // Pausar: congela el restante calculado sobre endAt.
      if (endAt !== null) {
        setSecondsLeft(Math.max(0, Math.round((endAt - Date.now()) / 1000)));
      }
      setEndAt(null);
      setRunning(false);
    } else {
      setEndAt(Date.now() + Math.max(1, secondsLeft) * 1000);
      setRunning(true);
    }
  }, [running, endAt, secondsLeft]);

  // Espacio = iniciar/pausar (salvo dentro de campos/botones interactivos,
  // donde el espacio conserva su comportamiento nativo).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== "Space") return;
      const el = e.target as HTMLElement | null;
      const tag = el?.tagName;
      if (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        tag === "SELECT" ||
        tag === "BUTTON" ||
        tag === "A" ||
        el?.isContentEditable
      )
        return;
      e.preventDefault();
      toggle();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);

  const reset = () => {
    setRunning(false);
    setEndAt(null);
    setSecondsLeft(durationFor(mode));
  };

  const skip = () => {
    const next: FocusMode = mode === "work" ? "break" : "work";
    setMode(next);
    setRunning(false);
    setEndAt(null);
    setSecondsLeft(durationFor(next));
  };

  const switchMode = (m: FocusMode | null) => {
    if (!m || m === mode) return;
    setMode(m);
    setRunning(false);
    setEndAt(null);
    setSecondsLeft(durationFor(m));
  };

  const applyWorkMin = (v: number) => {
    const n = Math.min(180, Math.max(1, Math.round(v) || DEFAULT_WORK));
    setWorkMin(n);
    localStorage.setItem(LS_WORK, String(n));
    if (!running && mode === "work") setSecondsLeft(n * 60);
  };

  const applyBreakMin = (v: number) => {
    const n = Math.min(180, Math.max(1, Math.round(v) || DEFAULT_BREAK));
    setBreakMin(n);
    localStorage.setItem(LS_BREAK, String(n));
    if (!running && mode === "break") setSecondsLeft(n * 60);
  };

  const todayKey = format(new Date(), "yyyy-MM-dd");
  const todaySessions = sessions.filter((s) => s.date === todayKey);
  const todayMinutes = todaySessions.reduce((acc, s) => acc + s.minutes, 0);
  const progress =
    ((durationFor(mode) - Math.max(0, secondsLeft)) / durationFor(mode)) * 100;

  return (
    <Box sx={{ maxWidth: 720, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} mb={3}>
        {t("p.taskx.focus.title")}
      </Typography>

      <Paper variant="outlined" sx={{ p: 3 }}>
        <Stack alignItems="center" spacing={2.5}>
          <ToggleButtonGroup
            size="small"
            exclusive
            value={mode}
            onChange={(_, m) => switchMode(m)}
            aria-label={t("p.taskx.focus.title")}
          >
            <ToggleButton value="work">{t("p.taskx.focus.work")}</ToggleButton>
            <ToggleButton value="break">{t("p.taskx.focus.break")}</ToggleButton>
          </ToggleButtonGroup>

          {/* Countdown circular con dígitos grandes */}
          <Box sx={{ position: "relative", display: "inline-flex" }}>
            <CircularProgress
              variant="determinate"
              value={progress}
              size={240}
              thickness={3}
              color={mode === "work" ? "primary" : "success"}
            />
            <Box
              sx={{
                position: "absolute",
                inset: 0,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Typography
                variant="h2"
                fontWeight={700}
                sx={{ fontVariantNumeric: "tabular-nums" }}
              >
                {fmt(secondsLeft)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {mode === "work" ? t("p.taskx.focus.work") : t("p.taskx.focus.break")}
              </Typography>
            </Box>
          </Box>

          <Typography variant="body2" color="text.secondary" noWrap>
            {selectedTask
              ? t("p.taskx.focus.focusedOn", { title: selectedTask.title })
              : t("p.taskx.focus.noTask")}
          </Typography>

          <Stack direction="row" spacing={1} alignItems="center">
            <Button
              variant="contained"
              size="large"
              startIcon={running ? <Pause size={18} /> : <Play size={18} />}
              onClick={toggle}
              sx={{ minWidth: 140 }}
            >
              {running ? t("p.taskx.focus.pause") : t("p.taskx.focus.start")}
            </Button>
            <Tooltip title={t("p.taskx.focus.reset")}>
              <span>
                <Button
                  variant="outlined"
                  onClick={reset}
                  aria-label={t("p.taskx.focus.reset")}
                >
                  <RotateCcw size={16} />
                </Button>
              </span>
            </Tooltip>
            <Tooltip title={t("p.taskx.focus.skip")}>
              <span>
                <Button
                  variant="outlined"
                  onClick={skip}
                  aria-label={t("p.taskx.focus.skip")}
                >
                  <SkipForward size={16} />
                </Button>
              </span>
            </Tooltip>
          </Stack>
          <Typography variant="caption" color="text.secondary">
            {t("p.taskx.focus.spaceHint")}
          </Typography>

          <Autocomplete
            size="small"
            fullWidth
            options={openTasks}
            value={selectedTask}
            getOptionLabel={(o) => o.title}
            isOptionEqualToValue={(a, b) => a.id === b.id}
            onChange={(_, v) => setSelectedTask(v)}
            renderInput={(params) => (
              <TextField {...params} label={t("p.taskx.focus.selectTask")} />
            )}
          />

          <Stack direction="row" spacing={2}>
            <TextField
              size="small"
              type="number"
              label={t("p.taskx.focus.workMin")}
              value={workMin}
              onChange={(e) => applyWorkMin(Number(e.target.value))}
              inputProps={{ min: 1, max: 180 }}
              sx={{ width: 160 }}
            />
            <TextField
              size="small"
              type="number"
              label={t("p.taskx.focus.breakMin")}
              value={breakMin}
              onChange={(e) => applyBreakMin(Number(e.target.value))}
              inputProps={{ min: 1, max: 180 }}
              sx={{ width: 160 }}
            />
          </Stack>
        </Stack>
      </Paper>

      {/* Estadísticas de hoy (localStorage) */}
      <Stack direction="row" spacing={2} mt={3} flexWrap="wrap" useFlexGap>
        <Chip
          icon={<Flame size={14} />}
          label={`${t("p.taskx.focus.todayPomodoros")}: ${todaySessions.length}`}
          variant="outlined"
        />
        <Chip
          icon={<Clock size={14} />}
          label={`${t("p.taskx.focus.todayMinutes")}: ${todayMinutes}`}
          variant="outlined"
        />
        <Chip
          icon={<CheckCircle2 size={14} />}
          label={`${t("p.taskx.focus.sessionsCompleted")}: ${cycleCount}`}
          variant="outlined"
        />
      </Stack>
    </Box>
  );
}
