import { useEffect, useState } from "react";
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
  Tooltip,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Grid,
} from "@mui/material";
import { Plus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/states";
import { risksApi, projectsApi, type ProjectRiskItem } from "../api/resources";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import { useProject } from "../auth/ProjectContext";

const LEVEL_ORDER = { low: 0, medium: 1, high: 2 } as const;
const LEVELS = ["low", "medium", "high"] as const;
const STATUSES = ["open", "mitigated", "closed", "realized"] as const;

// Celda de la matriz prob×impact: color + etiqueta (no solo color, WCAG)
function cellSeverity(p: number, i: number) {
  const s = p + i;
  return s >= 3
    ? { sev: "critical", bg: "#FFCDD2", fg: "#B71C1C" }
    : s === 2
      ? { sev: "high", bg: "#FFE0B2", fg: "#E65100" }
      : s === 1
        ? { sev: "medium", bg: "#FFF9C4", fg: "#F57F17" }
        : { sev: "low", bg: "#C8E6C9", fg: "#1B5E20" };
}

/**
 * Registro de riesgos por proyecto: tabla + matriz probabilidad × impacto.
 */
export default function RisksPage() {
  const { t } = useTranslation();
  const levelLabel = (l: string) => t(`p.collab.risks.level.${l}`, { defaultValue: l });
  const statusLabel = (s: string) => t(`p.collab.risks.status.${s}`, { defaultValue: s });
  const { project: ctxProject } = useProject();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [projectId, setProjectId] = useState<number | "">(ctxProject?.id ?? "");
  const [dialog, setDialog] = useState(false);
  const [form, setForm] = useState<Partial<ProjectRiskItem>>({
    title: "",
    description: "",
    probability: "medium",
    impact: "medium",
    status: "open",
    mitigation: "",
  });

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData) ? projectsData : [];

  // Preselecciona el primer proyecto — evita la vista sin proyecto
  // elegido (botón "Registrar riesgo" deshabilitado, tabla vacía).
  useEffect(() => {
    if (projectId === "" && projects.length > 0) {
      const first = projects[0] as { id?: number };
      if (first?.id != null) setProjectId(first.id);
    }
  }, [projects, projectId]);

  const { data: risksData } = useQuery({
    queryKey: ["project-risks", projectId],
    queryFn: () => risksApi.list(projectId ? Number(projectId) : undefined),
  });
  const risks = Array.isArray(risksData) ? risksData : [];

  const createMut = useMutation({
    mutationFn: () => risksApi.create({ ...form, project: Number(projectId) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["project-risks"] });
      setDialog(false);
      setForm({
        title: "",
        description: "",
        probability: "medium",
        impact: "medium",
        status: "open",
        mitigation: "",
      });
      notify.success(t("p.collab.risks.created"));
    },
    onError: () => notify.error(t("p.collab.risks.createError")),
  });

  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      risksApi.update(id, { status: status as ProjectRiskItem["status"] }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project-risks"] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => risksApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project-risks"] }),
  });

  const riskAt = (p: string, i: string) =>
    risks.filter((r) => r.probability === p && r.impact === i && r.status === "open");

  return (
    <Box>
      <PageHeader
        title={t("p.collab.risks.title")}
        description={t("p.collab.risks.desc")}
        breadcrumbs={[
          { label: t("p.collab.field.project") },
          { label: t("p.collab.risks.title") },
        ]}
        actions={
          <>
            <TextField
              select
              size="small"
              label={t("p.collab.field.project")}
              value={projectId}
              onChange={(e) =>
                setProjectId(e.target.value === "" ? "" : Number(e.target.value))
              }
              sx={{ minWidth: 200 }}
            >
              <MenuItem value="">{t("p.collab.risks.projectAll")}</MenuItem>
              {projects.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name}
                </MenuItem>
              ))}
            </TextField>
            <Button
              variant="contained"
              startIcon={<Plus size={15} />}
              onClick={() => setDialog(true)}
              disabled={projectId === ""}
            >
              {t("p.collab.risks.register")}
            </Button>
          </>
        }
      />

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle2" fontWeight={700} mb={1.5}>
              {t("p.collab.risks.matrixTitle")}
            </Typography>
            <Box
              component="table"
              sx={{ width: "100%", borderCollapse: "collapse", textAlign: "center" }}
            >
              <thead>
                <tr>
                  <th style={{ fontSize: 11, padding: 4 }}>
                    {t("p.collab.risks.matrixHeader")}
                  </th>
                  {LEVELS.map((i) => (
                    <th key={i} style={{ fontSize: 11, padding: 4 }}>
                      {levelLabel(i)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...LEVELS].reverse().map((p) => (
                  <tr key={p}>
                    <td style={{ fontSize: 11, padding: 4, fontWeight: 700 }}>
                      {levelLabel(p)}
                    </td>
                    {LEVELS.map((i) => {
                      const sev = cellSeverity(LEVEL_ORDER[p], LEVEL_ORDER[i]);
                      const cell = riskAt(p, i);
                      return (
                        <td
                          key={i}
                          style={{
                            background: sev.bg,
                            color: sev.fg,
                            padding: 12,
                            fontSize: 12,
                            fontWeight: 600,
                          }}
                        >
                          {t(`p.collab.risks.sev.${sev.sev}`)}
                          {cell.length > 0 && (
                            <Typography
                              component="div"
                              variant="caption"
                              fontWeight={700}
                            >
                              {t("p.collab.risks.riskCount", {
                                count: cell.length,
                              })}
                            </Typography>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </Box>
          </Paper>
        </Grid>

        <Grid item xs={12} md={8}>
          <Paper variant="outlined" sx={{ overflowX: "auto" }}>
            <Table size="small">
              <caption
                style={{
                  textAlign: "left",
                  padding: 8,
                  opacity: 0.7,
                  captionSide: "bottom",
                }}
              >
                {t("p.collab.risks.tableCaption")}
              </caption>
              <TableHead>
                <TableRow>
                  <TableCell>{t("p.collab.risks.colRisk")}</TableCell>
                  <TableCell>{t("p.collab.risks.colProb")}</TableCell>
                  <TableCell>{t("p.collab.risks.colImpact")}</TableCell>
                  <TableCell>{t("p.collab.risks.colSev")}</TableCell>
                  <TableCell>{t("p.collab.field.status")}</TableCell>
                  <TableCell>{t("p.collab.risks.colOwner")}</TableCell>
                  <TableCell align="right"></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {risks.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>
                      <Typography variant="body2" fontWeight={600}>
                        {r.title}
                      </Typography>
                      {r.mitigation && (
                        <Typography variant="caption" color="text.secondary">
                          {t("p.collab.risks.mitigation", { text: r.mitigation })}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>{levelLabel(r.probability)}</TableCell>
                    <TableCell>{levelLabel(r.impact)}</TableCell>
                    <TableCell>
                      <Tooltip
                        title={t("p.collab.risks.sevTip", {
                          p: levelLabel(r.probability),
                          i: levelLabel(r.impact),
                          s: r.severity,
                        })}
                      >
                        <Chip
                          size="small"
                          label={r.severity}
                          variant="outlined"
                          color={
                            r.severity >= 4
                              ? "error"
                              : r.severity >= 3
                                ? "warning"
                                : "default"
                          }
                        />
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      <TextField
                        select
                        size="small"
                        variant="standard"
                        value={r.status}
                        onChange={(e) =>
                          updateStatus.mutate({ id: r.id, status: e.target.value })
                        }
                        sx={{ minWidth: 110 }}
                      >
                        {STATUSES.map((k) => (
                          <MenuItem key={k} value={k}>
                            {statusLabel(k)}
                          </MenuItem>
                        ))}
                      </TextField>
                    </TableCell>
                    <TableCell>{r.owner_email ?? "—"}</TableCell>
                    <TableCell align="right">
                      <Tooltip title={t("p.collab.risks.deleteRisk")}>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={async () => {
                            if (
                              await confirm(
                                t("p.collab.risks.confirmDelete", {
                                  title: r.title,
                                }),
                                { confirmLabel: t("common.delete") },
                              )
                            )
                              deleteMut.mutate(r.id);
                          }}
                        >
                          <Trash2 size={15} />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
                {risks.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7}>
                      <EmptyState
                        title={t("p.collab.risks.emptyTitle")}
                        description={t("p.collab.risks.emptyDesc")}
                      />
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Paper>
        </Grid>
      </Grid>

      <Dialog open={dialog} onClose={() => setDialog(false)} fullWidth maxWidth="sm">
        <DialogTitle>{t("p.collab.risks.register")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField
              label={t("p.collab.field.title")}
              fullWidth
              autoFocus
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <TextField
              label={t("p.collab.field.description")}
              multiline
              minRows={2}
              fullWidth
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <Stack direction="row" spacing={1.5}>
              <TextField
                select
                label={t("p.collab.risks.probability")}
                fullWidth
                value={form.probability}
                onChange={(e) =>
                  setForm({
                    ...form,
                    probability: e.target.value as ProjectRiskItem["probability"],
                  })
                }
              >
                {LEVELS.map((l) => (
                  <MenuItem key={l} value={l}>
                    {levelLabel(l)}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                label={t("p.collab.risks.impact")}
                fullWidth
                value={form.impact}
                onChange={(e) =>
                  setForm({
                    ...form,
                    impact: e.target.value as ProjectRiskItem["impact"],
                  })
                }
              >
                {LEVELS.map((l) => (
                  <MenuItem key={l} value={l}>
                    {levelLabel(l)}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
            <TextField
              label={t("p.collab.risks.mitigationPlan")}
              multiline
              minRows={2}
              fullWidth
              value={form.mitigation}
              onChange={(e) => setForm({ ...form, mitigation: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={!form.title?.trim() || createMut.isPending}
            onClick={() => createMut.mutate()}
          >
            {t("p.collab.risks.registerShort")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
