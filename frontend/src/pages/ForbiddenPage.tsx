import { useNavigate } from "react-router-dom";
import { Box, Typography, Button, Stack } from "@mui/material";
import { ShieldOff, ArrowLeft, Home } from "lucide-react";
import { useTranslation } from "react-i18next";
import "../i18n";

/** 403: el usuario está autenticado pero sin permiso para el recurso. */
export default function ForbiddenPage() {
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
      <ShieldOff size={56} color="#ed6c02" />
      <Typography variant="h4" fontWeight={700} mt={2}>
        {t("p.auth.forbidden.title")}
      </Typography>
      <Typography variant="body1" color="text.secondary" mt={1} maxWidth={440}>
        {t("p.auth.forbidden.body")}
      </Typography>
      <Stack direction="row" spacing={1.5} mt={3}>
        <Button
          variant="outlined"
          startIcon={<ArrowLeft size={15} />}
          onClick={() => navigate(-1)}
        >
          {t("p.auth.forbidden.goBack")}
        </Button>
        <Button
          variant="contained"
          startIcon={<Home size={15} />}
          onClick={() => navigate("/app")}
        >
          {t("p.auth.goHome")}
        </Button>
      </Stack>
    </Box>
  );
}
