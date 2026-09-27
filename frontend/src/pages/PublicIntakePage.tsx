import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Box,
  Container,
  Typography,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  MenuItem,
  Button,
  Switch,
  FormControlLabel,
  Alert,
  Divider,
} from "@mui/material";
import { AlertTriangle, CheckCircle2, ClipboardList } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  intakePublicApi,
  IntakePublicError,
  type IntakePublicField,
} from "../api/featTask3";

/**
 * Formulario intake público (/intake/:token) — standalone, sin sesión.
 * El visitante no está autenticado: las llamadas van por fetch plano
 * (intakePublicApi) y la página no usa AppLayout.
 */
export default function PublicIntakePage() {
  const { token } = useParams<{ token: string }>();
  const { t } = useTranslation();
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, boolean>>({});
  const [submitted, setSubmitted] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["public-intake", token],
    queryFn: () => intakePublicApi.getSchema(token!),
    enabled: !!token,
    retry: false,
  });

  const submitMut = useMutation({
    mutationFn: (data: Record<string, unknown>) => intakePublicApi.submit(token!, data),
    onSuccess: () => setSubmitted(true),
  });

  const setValue = (name: string, v: unknown) => {
    setValues((prev) => ({ ...prev, [name]: v }));
    if (fieldErrors[name]) {
      setFieldErrors((prev) => ({ ...prev, [name]: false }));
    }
  };

  const isEmpty = (f: IntakePublicField, v: unknown): boolean => {
    if (f.type === "checkbox") return v !== true;
    if (f.type === "number") return v === undefined || v === "" || v === null;
    return v === undefined || String(v).trim() === "";
  };

  const submit = () => {
    const errs: Record<string, boolean> = {};
    for (const f of data?.schema ?? []) {
      if (f.required && isEmpty(f, values[f.name])) errs[f.name] = true;
    }
    setFieldErrors(errs);
    if (Object.keys(errs).length > 0) return;
    submitMut.mutate(values);
  };

  // 404/410 → enlace inválido o revocado; otro fallo → error genérico.
  const notFound =
    error instanceof IntakePublicError && (error.status === 404 || error.status === 410);
  const disabled = !!data && !data.enabled;
  const fatal = notFound || (!!error && !notFound) || disabled;

  return (
    <Box
      minHeight="100vh"
      bgcolor="background.default"
      display="flex"
      flexDirection="column"
      alignItems="center"
      py={6}
      px={2}
    >
      {/* Marca de la app */}
      <Stack direction="row" spacing={1} alignItems="center" mb={3}>
        <ClipboardList size={22} />
        <Typography variant="h6" fontWeight={800} letterSpacing={0.5}>
          TODOlist
        </Typography>
      </Stack>

      <Container maxWidth="sm" disableGutters>
        {isLoading && (
          <Box display="flex" flexDirection="column" alignItems="center" py={10} gap={2}>
            <CircularProgress />
            <Typography color="text.secondary">
              {t("p.public.intakePage.loading")}
            </Typography>
          </Box>
        )}

        {fatal && (
          <Paper variant="outlined" sx={{ p: { xs: 3, sm: 4 } }}>
            <Stack alignItems="center" spacing={1.5} py={4} textAlign="center">
              <AlertTriangle size={48} strokeWidth={1.2} />
              <Typography variant="h6" fontWeight={600}>
                {disabled
                  ? t("p.public.intakePage.disabledTitle")
                  : t("p.public.intakePage.errorTitle")}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {disabled
                  ? t("p.public.intakePage.disabledDesc")
                  : notFound
                    ? t("p.public.intakePage.notFoundDesc")
                    : t("p.public.intakePage.errorDesc")}
              </Typography>
            </Stack>
          </Paper>
        )}

        {data && data.enabled && submitted && (
          <Paper variant="outlined" sx={{ p: { xs: 3, sm: 4 } }}>
            <Stack alignItems="center" spacing={1.5} py={4} textAlign="center">
              <CheckCircle2 size={48} strokeWidth={1.2} color="#43a047" />
              <Typography variant="h6" fontWeight={600}>
                {t("p.public.intakePage.successTitle")}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {t("p.public.intakePage.successDesc")}
              </Typography>
            </Stack>
          </Paper>
        )}

        {data && data.enabled && !submitted && (
          <Paper variant="outlined" sx={{ p: { xs: 3, sm: 4 } }}>
            <Typography variant="h5" fontWeight={700} component="h1">
              {data.name}
            </Typography>
            {data.description && (
              <Typography variant="body2" color="text.secondary" mt={1}>
                {data.description}
              </Typography>
            )}
            <Divider sx={{ my: 2.5 }} />
            <Stack spacing={2.5}>
              {data.schema.map((f) => (
                <IntakeField
                  key={f.name}
                  field={f}
                  value={values[f.name]}
                  error={!!fieldErrors[f.name]}
                  errorText={t("p.public.intakePage.required")}
                  onChange={(v) => setValue(f.name, v)}
                />
              ))}
            </Stack>
            {submitMut.isError && (
              <Alert severity="error" sx={{ mt: 2 }}>
                {t("p.public.intakePage.submitError")}
              </Alert>
            )}
            <Button
              variant="contained"
              fullWidth
              size="large"
              sx={{ mt: 3 }}
              disabled={submitMut.isPending}
              onClick={submit}
            >
              {submitMut.isPending
                ? t("p.public.intakePage.submitting")
                : t("p.public.intakePage.submit")}
            </Button>
            <Divider sx={{ mt: 3, mb: 2 }} />
            <Typography
              variant="caption"
              color="text.disabled"
              display="block"
              textAlign="center"
            >
              {t("p.public.intakePage.footer")}
            </Typography>
          </Paper>
        )}
      </Container>
    </Box>
  );
}

function IntakeField({
  field,
  value,
  error,
  errorText,
  onChange,
}: {
  field: IntakePublicField;
  value: unknown;
  error: boolean;
  errorText: string;
  onChange: (v: unknown) => void;
}) {
  if (field.type === "checkbox") {
    return (
      <Box>
        <FormControlLabel
          control={
            <Switch checked={!!value} onChange={(e) => onChange(e.target.checked)} />
          }
          label={field.label + (field.required ? " *" : "")}
        />
        {error && (
          <Typography variant="caption" color="error" display="block">
            {errorText}
          </Typography>
        )}
      </Box>
    );
  }
  if (field.type === "select") {
    return (
      <TextField
        select
        label={field.label}
        required={field.required}
        error={error}
        helperText={error ? errorText : undefined}
        fullWidth
        value={(value as string) ?? ""}
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
      error={error}
      helperText={error ? errorText : undefined}
      fullWidth
      InputLabelProps={field.type === "date" ? { shrink: true } : undefined}
      value={value === undefined || value === null ? "" : String(value)}
      onChange={(e) =>
        onChange(
          field.type === "number"
            ? e.target.value === ""
              ? ""
              : Number(e.target.value)
            : e.target.value,
        )
      }
    />
  );
}
