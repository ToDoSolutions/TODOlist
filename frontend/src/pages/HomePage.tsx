import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useState } from "react";
import {
  Box,
  Typography,
  GridLegacy as Grid,
  Button,
  Stack,
  Paper,
  Chip,
  Divider,
  Skeleton,
  Menu,
  MenuItem,
  IconButton,
  Tooltip,
  FormControlLabel,
  Checkbox,
} from "@mui/material";
import {
  AlertTriangle,
  Ban,
  CheckSquare,
  Folder,
  Plus,
  Search,
  Zap,
  Activity as ActivityIcon,
  SlidersHorizontal,
} from "lucide-react";
import { isToday, parseISO } from "date-fns";
import { formatDateTimeShort, formatShort } from "../lib/dates";
import PageHeader from "../components/ui/PageHeader";
import MetricCard from "../components/ui/MetricCard";
import { EmptyState } from "../components/ui/states";
import { StatusBadge } from "../components/ui/badges";
import {
  tasksApi,
  projectsApi,
  notificationsApi,
  activityFeedApi,
  sprintsApi,
  type Sprint,
  type MyWorkTask,
} from "../api/resources";
import { useAuth } from "../auth/AuthContext";
import { useProject } from "../auth/ProjectContext";
import { useUiStore } from "../store/uiStore";

const HOME_MODULES: { key: string; labelKey: string }[] = [
  { key: "metrics", labelKey: "p.work.home.modules.metrics" },
  { key: "today", labelKey: "p.work.home.modules.today" },
  { key: "attention", labelKey: "p.work.home.modules.attention" },
  { key: "projects", labelKey: "p.work.home.modules.projects" },
  { key: "sprint", labelKey: "p.work.home.modules.sprint" },
  { key: "activity", labelKey: "p.work.home.modules.activity" },
];

/**
 * Inicio global: punto de entrada sin contexto de proyecto.
 * Distinto de Dashboard (métricas) y Mi trabajo (lista personal):
 * es el centro de atención — qué necesita acción ahora.
 */
export default function HomePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { setProject } = useProject();
  const homeHidden = useUiStore((s) => s.homeHiddenModules);
  const toggleHomeModule = useUiStore((s) => s.toggleHomeModule);
  const [customizeAnchor, setCustomizeAnchor] = useState<HTMLElement | null>(null);
  const showModule = (key: string) => !homeHidden.includes(key);

  const { data: myWork, isLoading } = useQuery({
    queryKey: ["my-work"],
    queryFn: tasksApi.myWork,
  });
  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const { data: unreadCount } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: notificationsApi.unreadCount,
  });
  const { data: activity } = useQuery({
    queryKey: ["activity-feed", 8],
    queryFn: () => activityFeedApi.list(8),
  });
  const { data: sprintsData } = useQuery({
    queryKey: ["sprints"],
    queryFn: sprintsApi.list,
  });

  const projects = Array.isArray(projectsData) ? projectsData : [];
  const sprints: Sprint[] = Array.isArray(sprintsData) ? sprintsData : [];
  const activeSprint = sprints.find((s) => s.state === "active");

  const overdue = myWork?.overdue ?? [];
  const dueToday = myWork?.due_today ?? [];
  const blocked = myWork?.blocked ?? [];
  const inProgress = myWork?.in_progress ?? [];
  const notifCount =
    typeof unreadCount === "number"
      ? unreadCount
      : ((unreadCount as { count?: number } | undefined)?.count ?? 0);

  const hour = new Date().getHours();
  const greeting = t(
    hour < 12
      ? "p.work.home.greeting.morning"
      : hour < 20
        ? "p.work.home.greeting.afternoon"
        : "p.work.home.greeting.evening",
  );
  const firstName = user?.email?.split("@")[0] ?? "";

  if (isLoading) {
    return (
      <Box>
        <Skeleton variant="text" width={320} height={48} />
        <Grid container spacing={2} mt={1}>
          {[0, 1, 2, 3].map((i) => (
            <Grid item xs={12} sm={6} md={3} key={i}>
              <Skeleton variant="rounded" height={110} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  const TaskRow = ({ task }: { task: MyWorkTask }) => (
    <Paper
      variant="outlined"
      sx={{ p: 1.5, cursor: "pointer", "&:hover": { borderColor: "primary.main" } }}
      onClick={() => navigate("/app/my-work")}
    >
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <Box flex={1} minWidth={0}>
          <Typography variant="body2" fontWeight={600} noWrap>
            {task.title}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {task.due_date
              ? t("p.work.home.dueOn", {
                  date: formatShort(task.due_date),
                })
              : t("p.work.home.noDate")}
            {task.project ? ` · ${task.project}` : ""}
          </Typography>
        </Box>
        <StatusBadge state={task.state} />
      </Stack>
    </Paper>
  );

  return (
    <Box>
      <PageHeader
        title={t("p.work.home.greetingLine", { greeting, name: firstName })}
        description={
          t("p.work.home.descToday", { count: dueToday.length }) +
          (overdue.length
            ? t("p.work.home.descOverdue", { count: overdue.length })
            : "") +
          (blocked.length ? t("p.work.home.descBlocked", { count: blocked.length }) : "")
        }
        actions={
          <>
            <Tooltip title={t("p.work.home.customize")}>
              <IconButton
                onClick={(e) => setCustomizeAnchor(e.currentTarget)}
                aria-label={t("p.work.home.customize")}
              >
                <SlidersHorizontal size={16} />
              </IconButton>
            </Tooltip>
            <Menu
              anchorEl={customizeAnchor}
              open={!!customizeAnchor}
              onClose={() => setCustomizeAnchor(null)}
            >
              <MenuItem disabled sx={{ fontWeight: 700, fontSize: 12 }}>
                {t("p.work.home.visibleModules")}
              </MenuItem>
              {HOME_MODULES.map((m) => (
                <MenuItem key={m.key} dense>
                  <FormControlLabel
                    control={
                      <Checkbox
                        size="small"
                        checked={showModule(m.key)}
                        onChange={() => toggleHomeModule(m.key)}
                      />
                    }
                    label={t(m.labelKey)}
                  />
                </MenuItem>
              ))}
            </Menu>
            <Button
              variant="outlined"
              startIcon={<Search size={15} />}
              onClick={() =>
                document.dispatchEvent(
                  new KeyboardEvent("keydown", { key: "k", ctrlKey: true }),
                )
              }
            >
              {t("common.search")}
            </Button>
            <Button
              variant="contained"
              startIcon={<Plus size={15} />}
              onClick={() => navigate("/app/inbox?new=1")}
            >
              {t("p.work.home.createTask")}
            </Button>
          </>
        }
      />

      {showModule("metrics") && (
        <Grid container spacing={2} mb={3}>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title={t("p.work.home.today")}
              value={dueToday.length}
              icon={<CheckSquare size={18} />}
              onClick={() => navigate("/app/my-work")}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title={t("p.work.home.overdue")}
              value={overdue.length}
              icon={<AlertTriangle size={18} />}
              color="error.main"
              onClick={() => navigate("/app/my-work")}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title={t("p.work.home.blocked")}
              value={blocked.length}
              icon={<Ban size={18} />}
              color="warning.main"
              onClick={() => navigate("/app/my-work")}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title={t("nav.notifications")}
              value={notifCount}
              icon={<Zap size={18} />}
              onClick={() => navigate("/app/notifications")}
            />
          </Grid>
        </Grid>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Stack spacing={3}>
            {showModule("today") && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle1" fontWeight={700} mb={1.5}>
                  {t("p.work.home.todayHeading")}
                </Typography>
                {dueToday.length === 0 && inProgress.length === 0 ? (
                  <EmptyState
                    title={t("p.work.home.clearDay")}
                    description={t("p.work.home.clearDayDesc")}
                  />
                ) : (
                  <Stack spacing={1}>
                    {[...dueToday, ...inProgress]
                      .filter(
                        (task, i, arr) =>
                          arr.findIndex((x) => x.id === task.id) === i
                      )
                      .slice(0, 8)
                      .map((task) => (
                        <TaskRow key={task.id} task={task} />
                      ))}
                  </Stack>
                )}
              </Paper>
            )}

            {showModule("attention") && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography
                  variant="subtitle1"
                  fontWeight={700}
                  mb={1.5}
                  color="error.main"
                >
                  {t("p.work.home.modules.attention")}
                </Typography>
                {overdue.length === 0 && blocked.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    {t("p.work.home.allGood")}
                  </Typography>
                ) : (
                  <Stack spacing={1}>
                    {[...overdue, ...blocked]
                      .filter(
                        (task, i, arr) =>
                          arr.findIndex((x) => x.id === task.id) === i
                      )
                      .slice(0, 8)
                      .map((task) => (
                        <TaskRow key={task.id} task={task} />
                      ))}
                  </Stack>
                )}
              </Paper>
            )}
          </Stack>
        </Grid>

        <Grid item xs={12} md={4}>
          <Stack spacing={3}>
            {showModule("projects") && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle1" fontWeight={700} mb={1.5}>
                  {t("p.work.home.modules.projects")}
                </Typography>
                {projects.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    {t("p.work.home.firstProject")}
                  </Typography>
                ) : (
                  <Stack spacing={0.5}>
                    {projects.slice(0, 5).map((p) => (
                      <Paper
                        key={p.id}
                        variant="outlined"
                        sx={{
                          p: 1,
                          cursor: "pointer",
                          "&:hover": { borderColor: p.color },
                        }}
                        onClick={() => {
                          setProject({ id: p.id, name: p.name, color: p.color });
                          navigate(`/app/project/${p.id}`);
                        }}
                      >
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <Folder size={16} color={p.color} />
                          <Typography variant="body2" fontWeight={600} flex={1} noWrap>
                            {p.name}
                          </Typography>
                          <Chip
                            size="small"
                            label={`${p.tasks_count}`}
                            sx={{ height: 18, fontSize: 10 }}
                          />
                        </Stack>
                      </Paper>
                    ))}
                  </Stack>
                )}
              </Paper>
            )}

            {showModule("sprint") && activeSprint && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle1" fontWeight={700} mb={0.5}>
                  {t("p.work.home.modules.sprint")}
                </Typography>
                <Typography variant="body2" fontWeight={600}>
                  {activeSprint.name}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {formatShort(activeSprint.start_date)} –{" "}
                  {formatShort(activeSprint.end_date)}
                  {isToday(parseISO(activeSprint.end_date)) &&
                    ` · ${t("p.work.home.endsToday")}`}
                </Typography>
              </Paper>
            )}

            {showModule("activity") && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle1" fontWeight={700} mb={1.5}>
                  <ActivityIcon size={14} style={{ verticalAlign: -2 }} />{" "}
                  {t("p.work.home.modules.activity")}
                </Typography>
                {!activity || activity.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    {t("p.work.home.noActivity")}
                  </Typography>
                ) : (
                  <Stack spacing={1} divider={<Divider />}>
                    {activity.slice(0, 6).map((a, i) => (
                      <Box key={i}>
                        <Typography variant="caption" color="text.secondary">
                          {a.actor ?? t("p.work.home.system")} ·{" "}
                          {formatDateTimeShort(a.created_at)}
                        </Typography>
                        <Typography variant="body2">{a.summary}</Typography>
                      </Box>
                    ))}
                  </Stack>
                )}
              </Paper>
            )}
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
}
