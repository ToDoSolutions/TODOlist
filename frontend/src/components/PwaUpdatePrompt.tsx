import { Snackbar, Button, IconButton, Stack, Typography } from "@mui/material";
import { RefreshCw, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useRegisterSW } from "virtual:pwa-register/react";

/**
 * Prompt de actualización PWA: cuando el service worker detecta una versión
 * nueva, ofrece recargar en vez de aplicar el cambio silenciosamente
 * (registerType "prompt" en vite.config.ts).
 */
export default function PwaUpdatePrompt() {
  const { t } = useTranslation();
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW();

  return (
    <Snackbar
      open={needRefresh}
      anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
      message={
        <Stack direction="row" spacing={1} alignItems="center">
          <RefreshCw size={18} />
          <Typography variant="body2">{t("p.shell.ui.pwa.updateAvailable")}</Typography>
        </Stack>
      }
      action={
        <Stack direction="row" spacing={1} alignItems="center">
          <Button color="primary" size="small" onClick={() => updateServiceWorker(true)}>
            {t("p.shell.ui.pwa.update")}
          </Button>
          <IconButton
            size="small"
            color="inherit"
            aria-label={t("p.shell.ui.pwa.updateLater")}
            onClick={() => setNeedRefresh(false)}
          >
            <X size={16} />
          </IconButton>
        </Stack>
      }
    />
  );
}
