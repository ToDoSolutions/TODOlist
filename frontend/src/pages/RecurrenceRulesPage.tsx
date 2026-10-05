import { formatDate } from "../lib/dates";
import { useMemo, useState } from "react";
import { RRule } from "rrule";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { TableSkeleton } from "../components/ui/skeletons";
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Paper,
  Button,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Stack,
} from "@mui/material";
import { Trash2, Plus, Repeat } from "lucide-react";
import { useTranslation } from "react-i18next";
import { recurrenceRulesApi } from "../api/resources";
import type { RecurrenceRuleItem } from "../types";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import PageHeader from "../components/ui/PageHeader";
import { ErrorState } from "../components/ui/states";

// Preview de próximas fechas según frecuencia elegida (module-level:
// constante, no depende del render)
const FREQ_MAP: Record<string, number> = {
  daily: RRule.DAILY,
  weekly: RRule.WEEKLY,
  monthly: RRule.MONTHLY,
  yearly: RRule.YEARLY,
};

export default function RecurrenceRulesPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const FREQ_LABELS: Record<string, string> = {
    daily: t("p.ops.recurrence.freq.daily"),
    weekly: t("p.ops.recurrence.freq.weekly"),
    monthly: t("p.ops.recurrence.freq.monthly"),
    yearly: t("p.ops.recurrence.freq.yearly"),
  };
  const confirm = useConfirm();
  const [open, setOpen] = useState(false);
  const [frequency, setFrequency] = useState("weekly");
  const [interval, setInterval] = useState(1);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["recurrence-rules"],
    queryFn: recurrenceRulesApi.list,
  });
  const rules = data || [];

  // Preview de las próximas 5 fechas según frecuencia+intervalo elegidos
  const nextDates = useMemo(() => {
    try {
      const freq = FREQ_MAP[frequency];
      if (freq === undefined || interval < 1) return [];
      return new RRule({ freq, interval, dtstart: new Date() }).all((_, i) => i < 5);
    } catch {
      return [];
    }
  }, [frequency, interval]);

  const createMutation = useMutation({
    mutationFn: () => recurrenceRulesApi.create({ frequency, interval }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recurrence-rules"] });
      setOpen(false);
      notify.success(t("p.ops.recurrence.created"));
    },
    onError: () => notify.error(t("p.ops.recurrence.createError")),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => recurrenceRulesApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recurrence-rules"] });
      notify.success(t("p.ops.recurrence.deleted"));
    },
  });

  if (isLoading) return <TableSkeleton />;
  if (isError)
    return (
      <Box maxWidth={900} mx="auto" mt={4}>
        <ErrorState
          title={t("p.ops.recurrence.loadError")}
          onRetry={() => void refetch()}
        />
      </Box>
    );

  return (
    <Box>
      <PageHeader
        title={t("p.ops.recurrence.title")}
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={16} />}
            onClick={() => setOpen(true)}
          >
            {t("p.ops.recurrence.new")}
          </Button>
        }
      />

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>{t("p.ops.recurrence.frequency")}</TableCell>
              <TableCell>{t("p.ops.recurrence.interval")}</TableCell>
              <TableCell>{t("p.ops.recurrence.occurrences")}</TableCell>
              <TableCell>{t("p.ops.recurrence.createdAt")}</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {rules.map((r: RecurrenceRuleItem) => (
              <TableRow key={r.id}>
                <TableCell>{r.id}</TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    label={FREQ_LABELS[r.frequency] || r.frequency}
                    icon={<Repeat size={14} />}
                  />
                </TableCell>
                <TableCell>
                  {t("p.ops.recurrence.everyInterval", { interval: r.interval })}
                </TableCell>
                <TableCell>{r.occurrences_generated}</TableCell>
                <TableCell>{formatDate(r.created_at)}</TableCell>
                <TableCell>
                  <IconButton
                    size="small"
                    color="error"
                    onClick={async () => {
                      if (
                        await confirm(t("p.ops.recurrence.confirmDelete"), {
                          confirmLabel: t("common.delete"),
                        })
                      )
                        deleteMutation.mutate(r.id);
                    }}
                    title={t("common.delete")}
                  >
                    <Trash2 size={16} />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
            {rules.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography color="text.secondary">
                    {t("p.ops.recurrence.empty")}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={open} onClose={() => setOpen(false)}>
        <DialogTitle>{t("p.ops.recurrence.newTitle")}</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            select
            label={t("p.ops.recurrence.frequency")}
            value={frequency}
            onChange={(e) => setFrequency(e.target.value)}
            sx={{ mt: 1 }}
            SelectProps={{ native: true }}
          >
            {Object.keys(FREQ_MAP).map((k) => (
              <option key={k} value={k}>
                {FREQ_LABELS[k]}
              </option>
            ))}
          </TextField>
          <TextField
            fullWidth
            label={t("p.ops.recurrence.intervalLabel")}
            type="number"
            value={interval}
            onChange={(e) => setInterval(Number(e.target.value))}
            sx={{ mt: 2 }}
            inputProps={{ min: 1 }}
          />
          {nextDates.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="caption" color="text.secondary">
                {t("p.ops.recurrence.nextDates")}
              </Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" sx={{ mt: 0.5 }}>
                {nextDates.map((d) => (
                  <Chip
                    key={d.toISOString()}
                    size="small"
                    variant="outlined"
                    label={formatDate(d)}
                  />
                ))}
              </Stack>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}