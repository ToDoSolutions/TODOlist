import { ReactNode } from "react";
import { Box, Button, Typography } from "@mui/material";
import { AlertTriangle, Inbox, Lock, RefreshCw, WifiOff } from "lucide-react";
import { useTranslation } from "react-i18next";

interface StateProps {
  title: string;
  description?: string;
  /** Acción principal del estado (ej. "Crear el primero", "Reintentar"). */
  action?: ReactNode;
  icon?: ReactNode;
}

function StateBox({ title, description, action, icon }: StateProps) {
  return (
    <Box
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      textAlign="center"
      py={8}
      px={3}
      role="status"
    >
      {icon && (
        <Box mb={2} color="text.disabled">
          {icon}
        </Box>
      )}
      <Typography variant="h6" fontWeight={600} gutterBottom>
        {title}
      </Typography>
      {description && (
        <Typography
          variant="body2"
          color="text.secondary"
          mb={action ? 3 : 0}
          maxWidth={420}
        >
          {description}
        </Typography>
      )}
      {action}
    </Box>
  );
}

/** Vacío inicial: nunca se ha creado contenido. Incluye CTA orientador. */
export function EmptyState(props: StateProps) {
  return <StateBox icon={<Inbox size={48} strokeWidth={1.2} />} {...props} />;
}

/** Vacío causado por filtros/búsqueda: distinto mensaje que el vacío inicial. */
export function EmptyFilterState(props: Omit<StateProps, "title"> & { title?: string }) {
  const { t } = useTranslation();
  return (
    <StateBox
      icon={<Inbox size={48} strokeWidth={1.2} />}
      title={t("common.emptyFilter.title")}
      description={t("common.emptyFilter.desc")}
      {...props}
    />
  );
}

/** Error recuperable con reintento. */
export function ErrorState({ onRetry, ...props }: StateProps & { onRetry?: () => void }) {
  const { t } = useTranslation();
  return (
    <StateBox
      icon={<AlertTriangle size={48} strokeWidth={1.2} />}
      action={
        props.action ??
        (onRetry && (
          <Button
            variant="outlined"
            startIcon={<RefreshCw size={16} />}
            onClick={onRetry}
          >
            {t("common.retry")}
          </Button>
        ))
      }
      {...props}
    />
  );
}

/** Sin permisos: distinto de error genérico. */
export function PermissionState(props: Omit<StateProps, "title"> & { title?: string }) {
  const { t } = useTranslation();
  return (
    <StateBox
      icon={<Lock size={48} strokeWidth={1.2} />}
      title={t("common.noAccess.title")}
      description={t("common.noAccess.desc")}
      {...props}
    />
  );
}

/** Modo offline: aviso de datos potencialmente obsoletos. */
export function OfflineState(props: Omit<StateProps, "title"> & { title?: string }) {
  const { t } = useTranslation();
  return (
    <StateBox
      icon={<WifiOff size={48} strokeWidth={1.2} />}
      title={t("common.offline.title")}
      description={t("common.offline.desc")}
      {...props}
    />
  );
}
