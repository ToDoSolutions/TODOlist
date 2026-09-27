import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Box,
  Container,
  Typography,
  CircularProgress,
  Paper,
  Chip,
  Stack,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from "@mui/material";
import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { fetchPublicShare, type SharedTaskItem } from "../api/featPublic";
import { formatDate } from "../lib/dates";
import {
  STATE_COLORS,
  PRIORITY_COLORS,
  type TaskState,
  type TaskPriority,
} from "../types";

/**
 * Vista pública de un proyecto compartido por enlace (/share/:token).
 * NO usa el cliente autenticado ni layouts protegidos: el visitante no
 * tiene sesión, así que el fetch es plano y la página es standalone.
 */
export default function SharePage() {
  const { token } = useParams<{ token: string }>();
  const { t } = useTranslation();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["public-share", token],
    queryFn: () => fetchPublicShare(token!),
    enabled: !!token,
    retry: false,
  });

  return (
    <Box minHeight="100vh" bgcolor="background.default" py={6}>
      <Container maxWidth="md">
        {isLoading && (
          <Box display="flex" flexDirection="column" alignItems="center" py={10} gap={2}>
            <CircularProgress />
            <Typography color="text.secondary">{t("p.public.share.loading")}</Typography>
          </Box>
        )}

        {isError && (
          <Box display="flex" flexDirection="column" alignItems="center" py={10} gap={1}>
            <AlertTriangle size={48} strokeWidth={1.2} />
            <Typography variant="h6" fontWeight={600}>
              {t("p.public.share.errorTitle")}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t("p.public.share.errorDesc")}
            </Typography>
          </Box>
        )}

        {data && (
          <Paper variant="outlined" sx={{ p: { xs: 2, sm: 4 } }}>
            <Typography variant="h4" fontWeight={700} component="h1">
              {data.project.name}
            </Typography>
            {data.project.description && (
              <Typography variant="body1" color="text.secondary" mt={1}>
                {data.project.description}
              </Typography>
            )}
            <Typography variant="caption" color="text.secondary" mt={1} display="block">
              {t("p.public.share.tasksCount", { count: data.tasks.length })}
            </Typography>
            <Divider sx={{ my: 2 }} />
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t("p.public.share.colTitle")}</TableCell>
                    <TableCell>{t("p.public.share.colState")}</TableCell>
                    <TableCell>{t("p.public.share.colPriority")}</TableCell>
                    <TableCell>{t("p.public.share.colDue")}</TableCell>
                    <TableCell>{t("p.public.share.colAssignee")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.tasks.map((task) => (
                    <SharedTaskRow key={task.id} task={task} />
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <Divider sx={{ mt: 3, mb: 2 }} />
            <Typography
              variant="caption"
              color="text.disabled"
              display="block"
              textAlign="center"
            >
              {t("p.public.share.footer")}
            </Typography>
          </Paper>
        )}
      </Container>
    </Box>
  );
}

function SharedTaskRow({ task }: { task: SharedTaskItem }) {
  const { t } = useTranslation();
  // El estado "review" del modelo se traduce con la clave task.state.in_review.
  const stateKey = task.state === "review" ? "in_review" : task.state;
  const stateLabel = t(`task.state.${stateKey}`, { defaultValue: task.state });
  const stateColor = STATE_COLORS[task.state as TaskState] ?? STATE_COLORS.backlog;
  const p = task.priority as TaskPriority;
  const priorityLabel =
    p >= 0 && p <= 5 ? t(`task.priority.p${p}`) : String(task.priority);
  const priorityColor = PRIORITY_COLORS[p] ?? PRIORITY_COLORS[5];

  return (
    <TableRow>
      <TableCell>
        <Typography variant="body2">{task.title}</Typography>
      </TableCell>
      <TableCell>
        <Chip
          size="small"
          label={stateLabel}
          variant="outlined"
          sx={{ borderColor: stateColor, color: stateColor }}
        />
      </TableCell>
      <TableCell>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              bgcolor: priorityColor,
              flexShrink: 0,
            }}
          />
          <Typography variant="body2">{priorityLabel}</Typography>
        </Stack>
      </TableCell>
      <TableCell>
        <Typography variant="body2" color="text.secondary">
          {formatDate(task.due_date) || "—"}
        </Typography>
      </TableCell>
      <TableCell>
        <Typography variant="body2" color="text.secondary">
          {task.assignee_email || "—"}
        </Typography>
      </TableCell>
    </TableRow>
  );
}
