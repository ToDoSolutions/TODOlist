import { useNavigate } from "react-router-dom";
import { Box, Typography, Button, Stack } from "@mui/material";
import { OctagonPause } from "lucide-react";
import { useTranslation } from "react-i18next";
import "../i18n";

/**
 * Workspace suspendido: la organización está pausada (facturación o admin).
 * Estado accesible dentro del layout para no perder el contexto de navegación.
 */
export default function SuspendedPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <Box
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      minHeight="60vh"
      textAlign="center"
      px={3}
    >
      <OctagonPause size={56} color="#9c27b0" />
      <Typography variant="h4" fontWeight={700} mt={2}>
        {t("p.auth.suspended.title")}
      </Typography>
      <Typography variant="body1" color="text.secondary" mt={1} maxWidth={440}>
        {t("p.auth.suspended.body")}
      </Typography>
      <Stack direction="row" spacing={1.5} mt={3}>
        <Button variant="contained" onClick={() => navigate("/app")}>
          {t("p.auth.goHome")}
        </Button>
        <Button variant="outlined" onClick={() => navigate("/app/admin/organizations")}>
          {t("p.auth.suspended.viewOrgs")}
        </Button>
      </Stack>
    </Box>
  );
}
