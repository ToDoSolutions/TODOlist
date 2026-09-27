import { useNavigate } from "react-router-dom";
import { Box, Typography, Button, Stack } from "@mui/material";
import { Search, Home, ArrowLeft } from "lucide-react";
import { useTranslation } from "react-i18next";
import "../i18n";

/**
 * 404: el recurso no existe o no tienes acceso (el backend devuelve 404
 * en ambos casos por seguridad — no se distingue para no filtrar existencia).
 */
export default function NotFoundPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <Box
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      minHeight="70vh"
      textAlign="center"
      px={3}
    >
      <Typography variant="h1" fontWeight={800} color="text.disabled" fontSize={96}>
        404
      </Typography>
      <Typography variant="h6" fontWeight={600} gutterBottom>
        {t("p.auth.notFound.title")}
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={3} maxWidth={420}>
        {t("p.auth.notFound.body")}
      </Typography>
      <Stack direction="row" spacing={1.5}>
        <Button
          variant="outlined"
          startIcon={<ArrowLeft size={15} />}
          onClick={() => navigate(-1)}
        >
          {t("p.auth.notFound.goBack")}
        </Button>
        <Button
          variant="outlined"
          startIcon={<Search size={15} />}
          onClick={() =>
            document.dispatchEvent(
              new KeyboardEvent("keydown", { key: "k", ctrlKey: true }),
            )
          }
        >
          {t("p.auth.notFound.search")}
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
