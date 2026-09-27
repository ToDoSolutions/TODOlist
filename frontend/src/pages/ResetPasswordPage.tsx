import { useState } from "react";
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Alert,
  Stack,
  IconButton,
  InputAdornment,
} from "@mui/material";
import { KeyRound, Eye, EyeOff, ArrowLeft } from "lucide-react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import "../i18n";
import { authApi } from "../api/auth";

/** Confirmación del reset: llega desde el enlace del email
 *  (/reset-password?uid=…&token=…). */
export default function ResetPasswordPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const uid = params.get("uid") || "";
  const token = params.get("token") || "";

  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const linkValid = !!uid && !!token;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pw.length < 8) {
      setError(t("p.auth.reset.errorShort"));
      return;
    }
    if (pw !== pw2) {
      setError(t("p.auth.reset.errorMismatch"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await authApi.confirmPasswordReset(uid, token, pw);
      setDone(true);
      setTimeout(() => navigate("/login", { replace: true }), 2500);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string | string[] } } })
        ?.response?.data?.error;
      setError(
        Array.isArray(msg) ? msg.join(" ") : msg || t("p.auth.reset.errorInvalid"),
      );
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
            <KeyRound size={40} color="#1976d2" />
            <Typography variant="h5" fontWeight={700} mt={1}>
              {t("p.auth.reset.newPassword")}
            </Typography>
          </Box>

          {!linkValid ? (
            <Alert severity="error">{t("p.auth.reset.incompleteLink")}</Alert>
          ) : done ? (
            <Alert severity="success">{t("p.auth.reset.success")}</Alert>
          ) : (
            <form onSubmit={submit}>
              <Stack spacing={2}>
                {error && <Alert severity="error">{error}</Alert>}
                <TextField
                  label={t("p.auth.reset.newPassword")}
                  required
                  fullWidth
                  autoFocus
                  type={show ? "text" : "password"}
                  value={pw}
                  onChange={(e) => setPw(e.target.value)}
                  autoComplete="new-password"
                  helperText={t("p.auth.reset.passwordHint")}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          size="small"
                          onClick={() => setShow((v) => !v)}
                          aria-label={
                            show
                              ? t("p.auth.reset.hidePassword")
                              : t("p.auth.reset.showPassword")
                          }
                        >
                          {show ? <EyeOff size={18} /> : <Eye size={18} />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />
                <TextField
                  label={t("p.auth.confirmPassword")}
                  required
                  fullWidth
                  type={show ? "text" : "password"}
                  value={pw2}
                  onChange={(e) => setPw2(e.target.value)}
                  autoComplete="new-password"
                />
                <Button type="submit" variant="contained" size="large" disabled={busy}>
                  {busy ? t("p.auth.reset.saving") : t("p.auth.reset.save")}
                </Button>
                <Typography variant="caption" color="text.secondary">
                  {t("p.auth.reset.sessionsNote")}
                </Typography>
              </Stack>
            </form>
          )}

          {!done && (
            <Button
              component={RouterLink}
              to="/login"
              size="small"
              startIcon={<ArrowLeft size={16} />}
            >
              {t("p.auth.backToLogin")}
            </Button>
          )}
        </Stack>
      </Paper>
    </Box>
  );
}
