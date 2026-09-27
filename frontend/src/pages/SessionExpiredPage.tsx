import { useNavigate, useSearchParams } from "react-router-dom";
import { Box, Typography, Button, Paper, Stack } from "@mui/material";
import { TimerOff } from "lucide-react";
import { useTranslation } from "react-i18next";
import "../i18n";

/**
 * Sesión expirada: destino cuando el refresh token falla (ver api/client.ts).
 * Conserva la ruta original en ?next= para volver tras el login.
 */
export default function SessionExpiredPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next") || "/app";

  return (
    <Box
      display="flex"
      alignItems="center"
      justifyContent="center"
      minHeight="100vh"
      bgcolor="background.default"
      px={3}
    >
      <Paper variant="outlined" sx={{ p: 5, maxWidth: 420, textAlign: "center" }}>
        <TimerOff size={48} color="#ed6c02" />
        <Typography variant="h5" fontWeight={700} mt={2}>
          {t("p.auth.sessionExpired.title")}
        </Typography>
        <Typography variant="body2" color="text.secondary" mt={1}>
          {t("p.auth.sessionExpired.body")}
        </Typography>
        <Stack spacing={1} mt={3}>
          <Button
            variant="contained"
            fullWidth
            onClick={() =>
              navigate(`/login?next=${encodeURIComponent(next)}`, { replace: true })
            }
          >
            {t("p.auth.sessionExpired.loginAgain")}
          </Button>
          <Typography variant="caption" color="text.secondary">
            {t("p.auth.sessionExpired.note")}
          </Typography>
        </Stack>
      </Paper>
    </Box>
  );
}
