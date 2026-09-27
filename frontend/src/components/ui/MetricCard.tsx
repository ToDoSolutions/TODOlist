import { ReactNode } from "react";
import { Box, Card, CardActionArea, Typography } from "@mui/material";
import { TrendingDown, TrendingUp } from "lucide-react";

interface Props {
  title: string;
  value: ReactNode;
  icon?: ReactNode;
  /** Diferencia respecto al período anterior: "+3" / "-2" */
  delta?: number | string;
  /** true si un delta positivo es malo (vencidas, errores) */
  invertDelta?: boolean;
  /** Enlace de drill-down. */
  onClick?: () => void;
  color?: string;
}

/**
 * Tarjeta de métrica con contexto: valor + delta + drill-down.
 * El número solo no informa; el contexto ("+3 vs semana anterior") sí.
 */
export default function MetricCard({
  title,
  value,
  icon,
  delta,
  invertDelta,
  onClick,
  color = "primary.main",
}: Props) {
  const deltaNum = typeof delta === "string" ? parseFloat(delta) : delta;
  const deltaBad =
    deltaNum !== undefined && !isNaN(deltaNum)
      ? invertDelta
        ? deltaNum > 0
        : deltaNum < 0
      : false;

  const content = (
    <Box p={2.5}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
        <Typography variant="body2" color="text.secondary" fontWeight={600}>
          {title}
        </Typography>
        {icon && (
          <Box color={color} display="flex">
            {icon}
          </Box>
        )}
      </Box>
      <Typography variant="h4" fontWeight={700}>
        {value}
      </Typography>
      {delta !== undefined && (
        <Box display="flex" alignItems="center" gap={0.5} mt={0.5}>
          {deltaNum !== undefined &&
            !isNaN(deltaNum) &&
            deltaNum !== 0 &&
            (deltaNum > 0 ? (
              <TrendingUp size={14} color={deltaBad ? "#F44336" : "#66BB6A"} />
            ) : (
              <TrendingDown size={14} color={deltaBad ? "#F44336" : "#66BB6A"} />
            ))}
          <Typography
            variant="caption"
            color={deltaBad ? "error.main" : "text.secondary"}
          >
            {typeof delta === "number" && delta > 0 ? `+${delta}` : delta} vs período
            anterior
          </Typography>
        </Box>
      )}
    </Box>
  );

  return (
    <Card>
      {onClick ? <CardActionArea onClick={onClick}>{content}</CardActionArea> : content}
    </Card>
  );
}
