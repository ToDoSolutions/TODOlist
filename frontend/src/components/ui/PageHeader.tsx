import { ReactNode } from "react";
import { Box, Breadcrumbs, Link, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";

export interface Crumb {
  label: string;
  to?: string;
}

interface Props {
  title: ReactNode;
  description?: ReactNode;
  breadcrumbs?: Crumb[];
  /** Acción primaria (botón contained) y secundarias a la derecha. */
  actions?: ReactNode;
  /** Contenido bajo el título: tabs, selector de vista, etc. */
  children?: ReactNode;
}

/**
 * Cabecera de página común: breadcrumbs + título + descripción +
 * acción primaria + tabs/vista. Todas las páginas deberían usarla para
 * que las acciones no cambien de posición entre pantallas.
 */
export default function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
  children,
}: Props) {
  return (
    <Box mb={3}>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Breadcrumbs sx={{ mb: 0.5 }} aria-label="breadcrumbs">
          {breadcrumbs.map((c, i) =>
            c.to && i < breadcrumbs.length - 1 ? (
              <Link
                key={i}
                component={RouterLink}
                to={c.to}
                color="text.secondary"
                underline="hover"
                variant="body2"
              >
                {c.label}
              </Link>
            ) : (
              <Typography key={i} variant="body2" color="text.primary">
                {c.label}
              </Typography>
            ),
          )}
        </Breadcrumbs>
      )}
      <Box
        display="flex"
        alignItems="flex-start"
        justifyContent="space-between"
        gap={2}
        flexWrap="wrap"
      >
        <Box minWidth={0}>
          <Typography variant="h5" fontWeight={700} component="h1">
            {title}
          </Typography>
          {description && (
            <Typography variant="body2" color="text.secondary" mt={0.5}>
              {description}
            </Typography>
          )}
        </Box>
        {actions && (
          <Box display="flex" gap={1} alignItems="center" flexShrink={0}>
            {actions}
          </Box>
        )}
      </Box>
      {children && <Box mt={2}>{children}</Box>}
    </Box>
  );
}
