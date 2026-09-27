import { ReactNode } from "react";
import { Box, Paper, Typography } from "@mui/material";

interface Props {
  title?: string;
  children: ReactNode;
}

/**
 * Zona de peligro: acciones destructivas separadas visualmente al final
 * de la página, con borde de error y sin mezclarse con acciones normales.
 */
export default function DangerZone({ title = "Zona de peligro", children }: Props) {
  return (
    <Paper
      variant="outlined"
      sx={{
        mt: 4,
        p: 2.5,
        borderColor: "error.main",
        borderRadius: 2,
        bgcolor: (t) =>
          t.palette.mode === "dark" ? "rgba(244,67,54,0.06)" : "rgba(244,67,54,0.03)",
      }}
    >
      <Typography variant="h6" fontWeight={600} color="error.main" mb={1.5}>
        {title}
      </Typography>
      <Box display="flex" flexDirection="column" gap={1.5}>
        {children}
      </Box>
    </Paper>
  );
}
