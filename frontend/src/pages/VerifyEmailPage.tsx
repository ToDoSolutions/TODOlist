import { useEffect, useRef, useState } from "react";
import {
  Box,
  Paper,
  Typography,
  Button,
  Stack,
  Alert,
  CircularProgress,
} from "@mui/material";
import { MailCheck, ArrowLeft } from "lucide-react";
import { Link as RouterLink, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import "../i18n";
import { authApi } from "../api/auth";

/** Destino del enlace de verificación de email (/verify-email?uid&token). */
export default function VerifyEmailPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const uid = params.get("uid") || "";
  const token = params.get("token") || "";
  const [result, setResult] = useState<"ok" | "error" | null>(null);
  const called = useRef(false);

  useEffect(() => {
    if (!uid || !token || called.current) return;
    called.current = true;
    authApi
      .verifyEmail(uid, token)
      .then(() => setResult("ok"))
      .catch(() => setResult("error"));
  }, [uid, token]);

  // Sin uid/token el enlace es inválido: estado derivado, no setState en effect
  const state = !uid || !token ? "error" : (result ?? "loading");

  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="100vh"
      p={2}
    >
      <Paper sx={{ p: 4, maxWidth: 420, width: "100%" }} variant="outlined">
        <Stack spacing={2.5} alignItems="center" textAlign="center">
          <MailCheck size={40} color="#1976d2" />
          <Typography variant="h5" fontWeight={700}>
            {t("p.auth.verifyEmail.title")}
          </Typography>

          {state === "loading" && <CircularProgress />}
          {state === "ok" && (
            <Alert severity="success" sx={{ width: "100%" }}>
              {t("p.auth.verifyEmail.success")}
            </Alert>
          )}
          {state === "error" && (
            <Alert severity="error" sx={{ width: "100%" }}>
              {t("p.auth.verifyEmail.error")}
            </Alert>
          )}

          <Button
            component={RouterLink}
            to="/app/profile"
            size="small"
            startIcon={<ArrowLeft size={16} />}
          >
            {t("p.auth.verifyEmail.goToProfile")}
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
}
