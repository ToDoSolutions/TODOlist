import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Typography,
  Stack,
  Paper,
  Button,
  TextField,
  MenuItem,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Divider,
  Grid,
} from "@mui/material";
import {
  Plus,
  CalendarClock,
  Users,
  CheckSquare,
  Trash2,
  Video,
  VideoOff,
  Copy,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { format, parseISO, isFuture } from "date-fns";
import { es } from "date-fns/locale";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/states";
import { meetingsApi, projectsApi, type MeetingItem } from "../api/resources";
import { meetingsVideoApi, type MeetingWithVideo } from "../api/featEnt";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";

/**
 * Reuniones: agenda, notas, decisiones y action items → tareas.
 */
export default function MeetingsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [dialog, setDialog] = useState(false);
  const [detail, setDetail] = useState<MeetingWithVideo | null>(null);
  const [embed, setEmbed] = useState(false);
  const [actionItem, setActionItem] = useState("");
  const [form, setForm] = useState({
    title: "",
    scheduled_at: "",
    duration_minutes: 30,
    project: "",
  });

  const { data: meetingsData } = useQuery({
    queryKey: ["meetings"],
    queryFn: () => meetingsApi.list(),
  });
  const meetings = (
    Array.isArray(meetingsData) ? meetingsData : []
  ) as MeetingWithVideo[];
  const upcoming = meetings.filter((m) => isFuture(parseISO(m.scheduled_at)));
  const past = meetings.filter((m) => !isFuture(parseISO(m.scheduled_at)));

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData) ? projectsData : [];

  const createMut = useMutation({
    mutationFn: () =>
      meetingsApi.create({
        title: form.title,
        scheduled_at: form.scheduled_at,
        duration_minutes: form.duration_minutes,
        project: form.project ? Number(form.project) : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["meetings"] });
      setDialog(false);
      setForm({ title: "", scheduled_at: "", duration_minutes: 30, project: "" });
      notify.success(t("p.collab.meetings.created"));
    },
    onError: () => notify.error(t("p.collab.meetings.createError")),
  });

  const saveNotes = useMutation({
    mutationFn: (m: MeetingItem) =>
      meetingsApi.update(m.id, { notes: m.notes, decisions: m.decisions }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["meetings"] });
      notify.success(t("p.collab.meetings.updated"));
    },
  });

  const createTask = useMutation({
    mutationFn: ({ id, title }: { id: number; title: string }) =>
      meetingsApi.createTask(id, title),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["meetings"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setActionItem("");
      notify.success(t("p.collab.meetings.taskCreated"));
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => meetingsApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["meetings"] });
      setDetail(null);
      notify.success(t("p.collab.meetings.deleted"));
    },
  });

  // Videollamada: POST /meetings/{id}/video/ (idempotente) y close_video/.
  const videoStart = useMutation({
    mutationFn: (id: number) => meetingsVideoApi.start(id),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["meetings"] });
      setDetail((d) => (d ? { ...d, video_url: res.url, video_room: res.room } : d));
      notify.success(t("p.ent.video.createdOk"));
    },
    onError: () => notify.error(t("p.ent.video.createError")),
  });

  const videoClose = useMutation({
    mutationFn: (id: number) => meetingsVideoApi.close(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["meetings"] });
      setDetail((d) => (d ? { ...d, video_url: null, video_room: "" } : d));
      setEmbed(false);
      notify.success(t("p.ent.video.endedOk"));
    },
    onError: () => notify.error(t("p.ent.video.endError")),
  });

  const copyVideoLink = () => {
    if (!detail?.video_url) return;
    void navigator.clipboard.writeText(detail.video_url);
    notify.success(t("p.ent.video.copied"));
  };

  const MeetingCard = ({ m }: { m: MeetingWithVideo }) => (
    <Paper
      variant="outlined"
      sx={{ p: 1.5, cursor: "pointer", "&:hover": { borderColor: "primary.main" } }}
      onClick={() => {
        setDetail(m);
        setEmbed(false);
      }}
    >
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <CalendarClock size={18} />
        <Box flex={1} minWidth={0}>
          <Typography variant="body2" fontWeight={600} noWrap>
            {m.title}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {format(parseISO(m.scheduled_at), "d MMM yyyy HH:mm", { locale: es })} ·{" "}
            {m.duration_minutes} min
          </Typography>
        </Box>
        {m.video_url && (
          <Button
            size="small"
            variant="outlined"
            component="a"
            href={m.video_url}
            target="_blank"
            rel="noopener noreferrer"
            startIcon={<Video size={14} />}
            onClick={(e) => e.stopPropagation()}
          >
            {t("p.ent.video.join")}
          </Button>
        )}
        {m.attendees_emails?.length > 0 && (
          <Chip
            size="small"
            icon={<Users size={11} />}
            label={m.attendees_emails.length}
            variant="outlined"
          />
        )}
        {m.tasks_ids?.length > 0 && (
          <Chip
            size="small"
            icon={<CheckSquare size={11} />}
            label={t("p.collab.meetings.actionsCount", {
              count: m.tasks_ids.length,
            })}
            variant="outlined"
            color="primary"
          />
        )}
      </Stack>
    </Paper>
  );

  return (
    <Box>
      <PageHeader
        title={t("p.collab.meetings.title")}
        description={t("p.collab.meetings.desc")}
        breadcrumbs={[
          { label: t("p.collab.meetings.breadcrumbCollab") },
          { label: t("p.collab.meetings.title") },
        ]}
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={15} />}
            onClick={() => setDialog(true)}
          >
            {t("p.collab.meetings.new")}
          </Button>
        }
      />

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Typography variant="subtitle1" fontWeight={700} mb={1.5}>
            {t("p.collab.meetings.upcoming")}
          </Typography>
          {upcoming.length === 0 ? (
            <EmptyState
              title={t("p.collab.meetings.emptyTitle")}
              description={t("p.collab.meetings.emptyDesc")}
            />
          ) : (
            <Stack spacing={1}>
              {upcoming.map((m) => (
                <MeetingCard key={m.id} m={m} />
              ))}
            </Stack>
          )}
        </Grid>
        <Grid item xs={12} md={6}>
          <Typography variant="subtitle1" fontWeight={700} mb={1.5}>
            {t("p.collab.meetings.recent")}
          </Typography>
          {past.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {t("p.collab.meetings.noPast")}
            </Typography>
          ) : (
            <Stack spacing={1}>
              {past.slice(0, 10).map((m) => (
                <MeetingCard key={m.id} m={m} />
              ))}
            </Stack>
          )}
        </Grid>
      </Grid>

      {/* Nueva reunión */}
      <Dialog open={dialog} onClose={() => setDialog(false)} fullWidth maxWidth="xs">
        <DialogTitle>{t("p.collab.meetings.new")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField
              label={t("p.collab.field.title")}
              fullWidth
              autoFocus
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <TextField
              label={t("p.collab.meetings.dateTime")}
              type="datetime-local"
              fullWidth
              InputLabelProps={{ shrink: true }}
              value={form.scheduled_at}
              onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })}
            />
            <TextField
              label={t("p.collab.meetings.duration")}
              type="number"
              fullWidth
              value={form.duration_minutes}
              inputProps={{ min: 5, step: 5 }}
              onChange={(e) =>
                setForm({ ...form, duration_minutes: Number(e.target.value) })
              }
            />
            <TextField
              select
              label={t("p.collab.field.project")}
              fullWidth
              value={form.project}
              onChange={(e) => setForm({ ...form, project: e.target.value })}
            >
              <MenuItem value="">{t("p.collab.meetings.noProject")}</MenuItem>
              {projects.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={!form.title.trim() || !form.scheduled_at}
            onClick={() => createMut.mutate()}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Detalle: notas, decisiones, action items */}
      <Dialog
        open={!!detail}
        onClose={() => {
          setDetail(null);
          setEmbed(false);
        }}
        fullWidth
        maxWidth="md"
      >
        {detail && (
          <>
            <DialogTitle>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Box flex={1}>{detail.title}</Box>
                <IconButton
                  size="small"
                  color="error"
                  aria-label={t("p.collab.meetings.deleteAria")}
                  onClick={async () => {
                    if (await confirm(t("p.collab.meetings.confirmDelete")))
                      deleteMut.mutate(detail.id);
                  }}
                >
                  <Trash2 size={16} />
                </IconButton>
              </Stack>
              <Typography variant="caption" color="text.secondary">
                {format(parseISO(detail.scheduled_at), "d MMM yyyy HH:mm", {
                  locale: es,
                })}{" "}
                ·{" "}
                {detail.attendees_emails?.join(", ") ||
                  t("p.collab.meetings.noAttendees")}
              </Typography>
            </DialogTitle>
            <DialogContent dividers>
              <Stack spacing={2.5}>
                {/* Videollamada de la reunión */}
                <Box>
                  <Typography variant="subtitle2" fontWeight={700} mb={1}>
                    {t("p.ent.video.sectionTitle")}
                  </Typography>
                  {detail.video_url ? (
                    <Stack spacing={1.5}>
                      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        <Button
                          size="small"
                          variant="contained"
                          component="a"
                          href={detail.video_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          startIcon={<Video size={15} />}
                        >
                          {t("p.ent.video.join")}
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          startIcon={<Copy size={15} />}
                          onClick={copyVideoLink}
                        >
                          {t("p.ent.video.copyLink")}
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => setEmbed((v) => !v)}
                        >
                          {embed ? t("p.ent.video.hideEmbed") : t("p.ent.video.embed")}
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          color="error"
                          startIcon={<VideoOff size={15} />}
                          disabled={videoClose.isPending}
                          onClick={() => videoClose.mutate(detail.id)}
                        >
                          {t("p.ent.video.end")}
                        </Button>
                      </Stack>
                      {embed && (
                        <Box
                          component="iframe"
                          src={detail.video_url}
                          allow="camera;microphone;fullscreen;display-capture"
                          sx={{
                            width: "100%",
                            height: 420,
                            border: 0,
                            borderRadius: 2,
                            bgcolor: "common.black",
                          }}
                        />
                      )}
                    </Stack>
                  ) : (
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<Video size={15} />}
                      disabled={videoStart.isPending}
                      onClick={() => videoStart.mutate(detail.id)}
                    >
                      {videoStart.isPending
                        ? t("p.ent.video.creating")
                        : t("p.ent.video.create")}
                    </Button>
                  )}
                </Box>
                <Divider />
                <TextField
                  label={t("p.collab.meetings.notes")}
                  multiline
                  minRows={4}
                  fullWidth
                  value={detail.notes}
                  onChange={(e) => setDetail({ ...detail, notes: e.target.value })}
                  helperText={t("p.collab.meetings.markdownHint")}
                />
                <TextField
                  label={t("p.collab.meetings.decisions")}
                  multiline
                  minRows={2}
                  fullWidth
                  value={detail.decisions}
                  onChange={(e) => setDetail({ ...detail, decisions: e.target.value })}
                />
                <Divider />
                <Box>
                  <Typography variant="subtitle2" fontWeight={700} mb={1}>
                    {t("p.collab.meetings.actionItems", {
                      count: detail.tasks_ids?.length ?? 0,
                    })}
                  </Typography>
                  <Stack direction="row" spacing={1}>
                    <TextField
                      size="small"
                      fullWidth
                      placeholder={t("p.collab.meetings.newAction")}
                      value={actionItem}
                      onChange={(e) => setActionItem(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && actionItem.trim()) {
                          e.preventDefault();
                          createTask.mutate({ id: detail.id, title: actionItem.trim() });
                        }
                      }}
                    />
                    <Button
                      variant="outlined"
                      size="small"
                      disabled={!actionItem.trim() || createTask.isPending}
                      onClick={() =>
                        createTask.mutate({ id: detail.id, title: actionItem.trim() })
                      }
                    >
                      {t("p.collab.meetings.createTask")}
                    </Button>
                  </Stack>
                </Box>
              </Stack>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setDetail(null)}>{t("common.close")}</Button>
              <Button
                variant="contained"
                onClick={() => saveNotes.mutate(detail)}
                disabled={saveNotes.isPending}
              >
                {t("p.collab.meetings.saveNotes")}
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </Box>
  );
}
