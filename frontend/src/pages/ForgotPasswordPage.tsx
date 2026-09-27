import { useState } from "react";
import { Box, Paper, Typography, TextField, Button, Alert, Stack } from "@mui/material";
import { Mail, ArrowLeft } from "lucide-react";
import { Link as RouterLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import "../i18n";
import { authApi } from "../api/auth";

/** Solicitud de recuperación de contraseña.
 * El backend siempre responde 200 para no filtrar emails existentes. */
export default function ForgotPasswordPage() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.includes("@")) {
      setError(t("p.auth.forgot.errorInvalidEmail"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await authApi.requestPasswordReset(email);
      setSent(true);
    } catch {
      setError(t("p.auth.forgot.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="100vh"
      p={2}
    >
      <Paper sx={{ p: 4, maxWidth: 420, width: "100%" }} variant="outlined">
        <Stack spacing={2.5}>
          <Box textAlign="center">
            <Mail size={40} color="#1976d2" />
            <Typography variant="h5" fontWeight={700} mt={1}>
              {t("p.auth.forgot.title")}
            </Typography>
          </Box>

          {sent ? (
            <Alert severity="success">{t("p.auth.forgot.sent")}</Alert>
          ) : (
            <form onSubmit={submit}>
              <Stack spacing={2}>
                <Typography variant="body2" color="text.secondary">
                  {t("p.auth.forgot.subtitle")}
                </Typography>
                {error && <Alert severity="error">{error}</Alert>}
                <TextField
                  label={t("p.auth.email")}
                  type="email"
                  value={email}
                  required
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  autoFocus
                  fullWidth
                />
                <Button type="submit" variant="contained" size="large" disabled={busy}>
                  {busy ? t("p.auth.forgot.sending") : t("p.auth.forgot.send")}
                </Button>
              </Stack>
            </form>
          )}

          <Button
            component={RouterLink}
            to="/login"
            size="small"
            startIcon={<ArrowLeft size={16} />}
          >
            {t("p.auth.backToLogin")}
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
}
