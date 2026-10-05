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
  Switch,
  FormControlLabel,
  Divider,
  Grid,
  Checkbox,
} from "@mui/material";
import {
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  Copy,
  RefreshCw,
  Link2,
  Inbox,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/states";
import { formatDate } from "../lib/dates";
import {
  intakeFormsApi,
  intakeSubmissionsApi,
  projectsApi,
  intakeFields,
  type IntakeFormItem,
  type IntakeFormField,
} from "../api/resources";
import { intakePublicApi } from "../api/featPublic";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";

// public_token lo expone el backend en GET /api/intake-forms/ pero el tipo
// IntakeFormItem vive en resources.ts (fuera de este cambio).
type IntakeFormWithToken = IntakeFormItem & { public_token?: string };

const FIELD_TYPES = ["text", "number", "date", "select", "checkbox"] as const;

/**
 * Formularios intake: portales de solicitud que crean tareas
 * sin dar acceso al proyecto al solicitante.
 */
export default function IntakeFormsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [builder, setBuilder] = useState<IntakeFormItem | "new" | null>(null);
  const [preview, setPreview] = useState<IntakeFormItem | null>(null);
  const [submissionsFor, setSubmissionsFor] = useState<IntakeFormItem | null>(null);
  const [previewValues, setPreviewValues] = useState<Record<string, unknown>>({});

  const { data: formsData } = useQuery({
    queryKey: ["intake-forms"],
    queryFn: () => intakeFormsApi.list(),
  });
  const forms = Array.isArray(formsData) ? formsData : [];

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData) ? projectsData : [];

  const saveMut = useMutation({
    mutationFn: (f: IntakeFormItem) =>
      f.id ? intakeFormsApi.update(f.id, f) : intakeFormsApi.create(f),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["intake-forms"] });
      setBuilder(null);
      notify.success(t("p.ops.intake.saved"));
    },
    onError: (e: unknown) => {
      const data = (e as { response?: { data?: { schema?: string[] } } })?.response?.data;
      notify.error(data?.schema?.[0] ?? t("p.ops.intake.saveError"));
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => intakeFormsApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["intake-forms"] }),
  });

  const rotateMut = useMutation({
    mutationFn: (id: number) => intakePublicApi.rotateToken(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["intake-forms"] });
      notify.success(t("p.public.intake.rotated"));
    },
    onError: () => notify.error(t("p.public.intake.rotateError")),
  });

  const publicUrl = (token: string) =>
    `${window.location.origin}/intake/${token}`;

  const copyPublicUrl = (token: string) => {
    void navigator.clipboard.writeText(publicUrl(token));
    notify.success(t("p.public.intake.copied"));
  };

  const regenerate = async (f: IntakeFormWithToken) => {
    if (
        await confirm(t("p.public.intake.confirmRegenerate", { name: f.name }), {
          confirmLabel: t("p.public.intake.regenerate"),
        })
      )
      rotateMut.mutate(f.id);
  };

  const submitMut = useMutation({
    mutationFn: ({ id, values }: { id: number; values: Record<string, unknown> }) =>
      intakeFormsApi.submit(id, values),
    onSuccess: () => {
      setPreview(null);
      setPreviewValues({});
      notify.success(t("p.ops.intake.submitted"));
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: () => notify.error(t("p.ops.intake.submitError")),
  });

  return (
    <Box>
      <PageHeader
        title={t("p.ops.intake.title")}
        description={t("p.ops.intake.description")}
        breadcrumbs={[
          { label: t("p.ops.project") },
          { label: t("p.ops.intake.breadcrumb") },
        ]}
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={15} />}
            onClick={() => setBuilder("new")}
          >
            {t("p.ops.intake.new")}
          </Button>
        }
      />

      {forms.length === 0 ? (
        <EmptyState
          title={t("p.ops.intake.emptyTitle")}
          description={t("p.ops.intake.emptyDesc")}
          action={
            <Button variant="contained" onClick={() => setBuilder("new")}>
              {t("p.ops.intake.createFirst")}
            </Button>
          }
        />
      ) : (
        <Grid container spacing={2}>
          {forms.map((f) => (
            <Grid item xs={12} sm={6} md={4} key={f.id}>
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Stack direction="row" alignItems="flex-start" spacing={1}>
                  <Box flex={1}>
                    <Typography variant="subtitle2" fontWeight={700}>
                      {f.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {t("p.ops.intake.fieldsCount", {
                        count: intakeFields(f.schema).length,
                      })}{" "}
                      ·{" "}
                      {t("p.ops.intake.submissionsCount", {
                        count: f.submissions_count ?? 0,
                      })}
                    </Typography>
                  </Box>
                  <Chip
                    size="small"
                    label={
                      f.enabled ? t("p.ops.intake.active") : t("p.ops.intake.inactive")
                    }
                    color={f.enabled ? "success" : "default"}
                    variant="outlined"
                  />
                </Stack>
                <Stack direction="row" spacing={0.5} mt={1.5}>
                  <Button size="small" onClick={() => setPreview(f)}>
                    {t("p.ops.intake.preview")}
                  </Button>
                  <Button
                    size="small"
                    startIcon={<Inbox size={13} />}
                    disabled={(f.submissions_count ?? 0) === 0}
                    onClick={() => setSubmissionsFor(f)}
                  >
                    {t("p.ops.intake.submissions")}
                  </Button>
                  <Button size="small" onClick={() => setBuilder(f)}>
                    {t("common.edit")}
                  </Button>
                  <Box flex={1} />
                  <IconButton
                    size="small"
                    color="error"
                    aria-label={t("common.delete")}
                    onClick={async () => {
                      if (
                        await confirm(
                          t("p.ops.intake.confirmDelete", { name: f.name }),
                          { confirmLabel: t("common.delete") },
                        )
                      )
                        deleteMut.mutate(f.id);
                    }}
                  >
                    <Trash2 size={15} />
                  </IconButton>
                </Stack>
                <Divider sx={{ my: 1.5 }} />
                <Stack direction="row" spacing={0.5} alignItems="center" mb={0.5}>
                  <Link2 size={13} />
                  <Typography variant="caption" fontWeight={700} color="text.secondary">
                    {t("p.public.intake.publicLink")}
                  </Typography>
                </Stack>
                {(f as IntakeFormWithToken).public_token ? (
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <TextField
                      size="small"
                      fullWidth
                      value={publicUrl((f as IntakeFormWithToken).public_token!)}
                      InputProps={{ readOnly: true }}
                      onFocus={(e) => e.target.select()}
                    />
                    <IconButton
                      size="small"
                      aria-label={t("p.public.intake.copy")}
                      onClick={() =>
                        copyPublicUrl((f as IntakeFormWithToken).public_token!)
                      }
                    >
                      <Copy size={15} />
                    </IconButton>
                    <IconButton
                      size="small"
                      aria-label={t("p.public.intake.regenerate")}
                      disabled={rotateMut.isPending}
                      onClick={() => void regenerate(f as IntakeFormWithToken)}
                    >
                      <RefreshCw size={15} />
                    </IconButton>
                  </Stack>
                ) : (
                  <Button
                    size="small"
                    variant="outlined"
                    disabled={rotateMut.isPending}
                    onClick={() => rotateMut.mutate(f.id)}
                  >
                    {t("p.public.intake.generate")}
                  </Button>
                )}
              </Paper>
            </Grid>
          ))}
        </Grid>
      )}

      {builder && (
        <FormBuilder
          initial={builder === "new" ? null : builder}
          projects={projects}
          onClose={() => setBuilder(null)}
          onSave={(f) => saveMut.mutate(f)}
          saving={saveMut.isPending}
        />
      )}

      {submissionsFor && (
        <SubmissionsDialog
          form={submissionsFor}
          onClose={() => setSubmissionsFor(null)}
        />
      )}

      <Dialog open={!!preview} onClose={() => setPreview(null)} fullWidth maxWidth="sm">
        {preview && (
          <>
            <DialogTitle>{preview.name}</DialogTitle>
            <DialogContent dividers>
              <Typography variant="body2" color="text.secondary" mb={2}>
                {preview.description}
              </Typography>
              <Stack spacing={2}>
                {intakeFields(preview.schema).map((f) => (
                  <PreviewField
                    key={f.name}
                    field={f}
                    value={previewValues[f.name]}
                    onChange={(v) => setPreviewValues({ ...previewValues, [f.name]: v })}
                  />
                ))}
              </Stack>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setPreview(null)}>{t("common.close")}</Button>
              <Button
                variant="contained"
                disabled={submitMut.isPending}
                onClick={() =>
                  submitMut.mutate({ id: preview.id, values: previewValues })
                }
              >
                {t("p.ops.intake.submit")}
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </Box>
  );
}

function SubmissionsDialog({
  form,
  onClose,
}: {
  form: IntakeFormItem;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: ["intake-submissions", form.id],
    queryFn: () => intakeSubmissionsApi.list(form.id),
  });
  const submissions = Array.isArray(data) ? data : [];

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>{t("p.ops.intake.submissionsTitle", { name: form.name })}</DialogTitle>
      <DialogContent dividers>
        {isLoading ? (
          <Typography variant="body2" color="text.secondary">
            {t("common.loading")}
          </Typography>
        ) : submissions.length === 0 ? (
          <EmptyState
            title={t("p.ops.intake.submissionsEmpty")}
            description={t("p.ops.intake.submissionsEmptyDesc")}
          />
        ) : (
          <Stack spacing={1.5}>
            {submissions.map((s) => (
              <Paper key={s.id} variant="outlined" sx={{ p: 1.5 }}>
                <Stack
                  direction="row"
                  alignItems="center"
                  spacing={1}
                  flexWrap="wrap"
                  useFlexGap
                >
                  <Typography variant="caption" color="text.secondary">
                    {formatDate(s.created_at)}
                  </Typography>
                  <Typography variant="caption" fontWeight={600}>
                    {s.submitted_by_email}
                  </Typography>
                  <Box flex={1} />
                  {s.task_id && (
                    <Chip
                      size="small"
                      variant="outlined"
                      label={`#${s.task_id} ${s.task_title ?? ""}`.trim()}
                    />
                  )}
                </Stack>
                <Stack spacing={0.25} mt={1}>
                  {Object.entries(s.data ?? {}).map(([k, v]) => (
                    <Typography key={k} variant="body2">
                      <Box component="span" fontWeight={600}>
                        {k}:
                      </Box>{" "}
                      {typeof v === "object" ? JSON.stringify(v) : String(v)}
                    </Typography>
                  ))}
                </Stack>
              </Paper>
            ))}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("common.close")}</Button>
      </DialogActions>
    </Dialog>
  );
}

function PreviewField({
  field,
  value,
  onChange,
}: {
  field: IntakeFormField;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  if (field.type === "checkbox") {
    return (
      <FormControlLabel
        control={
          <Checkbox checked={!!value} onChange={(e) => onChange(e.target.checked)} />
        }
        label={field.label + (field.required ? " *" : "")}
      />
    );
  }
  if (field.type === "select") {
    return (
      <TextField
        select
        label={field.label}
        required={field.required}
        fullWidth
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      >
        {(field.options ?? []).map((o) => (
          <MenuItem key={o} value={o}>
            {o}
          </MenuItem>
        ))}
      </TextField>
    );
  }
  return (
    <TextField
      label={field.label}
      type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
      required={field.required}
      fullWidth
      InputLabelProps={field.type === "date" ? { shrink: true } : undefined}
      value={(value as string) ?? ""}
      onChange={(e) =>
        onChange(field.type === "number" ? Number(e.target.value) : e.target.value)
      }
    />
  );
}

function FormBuilder({
  initial,
  projects,
  onClose,
  onSave,
  saving,
}: {
  initial: IntakeFormItem | null;
  projects: { id: number; name: string }[];
  onClose: () => void;
  onSave: (f: IntakeFormItem) => void;
  saving: boolean;
}) {
  const { t } = useTranslation();
  const FIELD_LABEL: Record<string, string> = {
    text: t("p.ops.intake.fieldType.text"),
    number: t("p.ops.intake.fieldType.number"),
    date: t("p.ops.date"),
    select: t("p.ops.intake.fieldType.select"),
    checkbox: t("p.ops.intake.fieldType.checkbox"),
  };
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [project, setProject] = useState<number | "">(initial?.project ?? "");
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
  const [fields, setFields] = useState<IntakeFormField[]>(
    (initial ? intakeFields(initial.schema) : null) ?? [
      {
        name: "titulo",
        label: t("p.ops.intake.defaultFieldLabel"),
        type: "text",
        required: true,
      },
    ],
  );

  const moveField = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= fields.length) return;
    const next = [...fields];
    [next[i], next[j]] = [next[j]!, next[i]!];
    setFields(next);
  };

  const updateField = (i: number, patch: Partial<IntakeFormField>) =>
    setFields(fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f)));

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>
        {initial ? t("p.ops.intake.editTitle") : t("p.ops.intake.new")}
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2.5}>
          <Stack direction="row" spacing={1.5}>
            <TextField
              label={t("common.name")}
              fullWidth
              autoFocus
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <TextField
              select
              label={t("p.ops.intake.targetProject")}
              required
              sx={{ minWidth: 200 }}
              value={project}
              onChange={(e) => setProject(Number(e.target.value))}
            >
              {projects.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          <TextField
            label={t("p.ops.description")}
            multiline
            minRows={2}
            fullWidth
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <FormControlLabel
            control={
              <Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
            }
            label={t("p.ops.intake.enabledLabel")}
          />
          <Divider />
          <Typography variant="subtitle2" fontWeight={700}>
            {t("p.ops.intake.fieldsTitle")}
          </Typography>
          {fields.map((f, i) => (
            <Paper key={i} variant="outlined" sx={{ p: 1.5 }}>
              <Stack
                direction="row"
                spacing={1}
                alignItems="center"
                flexWrap="wrap"
                useFlexGap
              >
                <TextField
                  size="small"
                  label={t("p.ops.intake.fieldName")}
                  value={f.name}
                  onChange={(e) =>
                    updateField(i, { name: e.target.value.replace(/\W/g, "_") })
                  }
                  sx={{ width: 150 }}
                />
                <TextField
                  size="small"
                  label={t("p.ops.intake.fieldLabel")}
                  value={f.label}
                  onChange={(e) => updateField(i, { label: e.target.value })}
                  sx={{ flex: 1, minWidth: 150 }}
                />
                <TextField
                  select
                  size="small"
                  label={t("p.ops.type")}
                  value={f.type}
                  onChange={(e) => updateField(i, { type: e.target.value })}
                  sx={{ width: 130 }}
                >
                  {FIELD_TYPES.map((tp) => (
                    <MenuItem key={tp} value={tp}>
                      {FIELD_LABEL[tp]}
                    </MenuItem>
                  ))}
                </TextField>
                <FormControlLabel
                  control={
                    <Checkbox
                      size="small"
                      checked={!!f.required}
                      onChange={(e) => updateField(i, { required: e.target.checked })}
                    />
                  }
                  label={t("p.ops.intake.required")}
                />
                <IconButton
                  size="small"
                  onClick={() => moveField(i, -1)}
                  disabled={i === 0}
                  aria-label={t("p.ops.intake.moveUp")}
                >
                  <ArrowUp size={14} />
                </IconButton>
                <IconButton
                  size="small"
                  onClick={() => moveField(i, 1)}
                  disabled={i === fields.length - 1}
                  aria-label={t("p.ops.intake.moveDown")}
                >
                  <ArrowDown size={14} />
                </IconButton>
                <IconButton
                  size="small"
                  color="error"
                  aria-label={t("p.ops.intake.removeField")}
                  onClick={() => setFields(fields.filter((_, idx) => idx !== i))}
                >
                  <Trash2 size={14} />
                </IconButton>
              </Stack>
              {f.type === "select" && (
                <TextField
                  size="small"
                  fullWidth
                  sx={{ mt: 1 }}
                  label={t("p.ops.intake.optionsLabel")}
                  value={(f.options ?? []).join(", ")}
                  onChange={(e) =>
                    updateField(i, {
                      options: e.target.value
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                />
              )}
            </Paper>
          ))}
          <Button
            size="small"
            startIcon={<Plus size={14} />}
            variant="outlined"
            sx={{ alignSelf: "flex-start" }}
            onClick={() =>
              setFields([
                ...fields,
                { name: `campo_${fields.length + 1}`, label: "", type: "text" },
              ])
            }
          >
            {t("p.ops.intake.addField")}
          </Button>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("common.cancel")}</Button>
        <Button
          variant="contained"
          disabled={!name.trim() || project === "" || fields.length === 0 || saving}
          onClick={() =>
            onSave({
              ...(initial ?? {}),
              name,
              description,
              project: Number(project),
              enabled,
              schema: fields,
            } as IntakeFormItem)
          }
        >
          {t("common.save")}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
