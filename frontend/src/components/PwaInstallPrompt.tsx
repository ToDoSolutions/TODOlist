import { useEffect, useState } from "react";
import { Snackbar, Button, IconButton, Stack, Typography } from "@mui/material";
import { Download, WifiOff, X } from "lucide-react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export default function PwaInstallPrompt() {
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [showInstall, setShowInstall] = useState(false);
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
  const [showOffline, setShowOffline] = useState(false);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setInstallEvent(e as BeforeInstallPromptEvent);
      setShowInstall(true);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  useEffect(() => {
    const onOffline = () => { setIsOffline(true); setShowOffline(true); };
    const onOnline = () => { setIsOffline(false); setShowOffline(false); };
    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    return () => {
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
    };
  }, []);

  const handleInstall = async () => {
    if (!installEvent) return;
    await installEvent.prompt();
    await installEvent.userChoice;
    setInstallEvent(null);
    setShowInstall(false);
  };

  return (
    <>
      <Snackbar
        open={showInstall}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
        message="Instala TODOlist como app"
        action={
          <Stack direction="row" spacing={1} alignItems="center">
            <Button color="primary" size="small" startIcon={<Download size={16} />} onClick={handleInstall}>
              Instalar
            </Button>
            <IconButton size="small" color="inherit" onClick={() => setShowInstall(false)}>
              <X size={16} />
            </IconButton>
          </Stack>
        }
      />
      <Snackbar
        open={showOffline && isOffline}
        anchorOrigin={{ vertical: "top", horizontal: "center" }}
        message={
          <Stack direction="row" spacing={1} alignItems="center">
            <WifiOff size={18} />
            <Typography variant="body2">Sin conexión - modo offline</Typography>
          </Stack>
        }
        action={
          <IconButton size="small" color="inherit" onClick={() => setShowOffline(false)}>
            <X size={16} />
          </IconButton>
        }
      />
    </>
  );
}
