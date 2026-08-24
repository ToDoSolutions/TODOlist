import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { advancedMetricsApi, sprintsApi } from "../api/resources";
import { Box, Typography, CircularProgress, Paper, Select, MenuItem, FormControl, InputLabel } from "@mui/material";

export default function BurndownPage() {
  const [sprintId, setSprintId] = useState<number | "">("");
  const { data: sprintsData } = useQuery({ queryKey: ["sprints"], queryFn: sprintsApi.list });
  const sprints: any[] = sprintsData || [];

  const { data, isLoading } = useQuery({
    queryKey: ["burndown", sprintId],
    queryFn: () => advancedMetricsApi.burndown(Number(sprintId)),
    enabled: !!sprintId,
  });

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Burndown Chart</Typography>
      <FormControl sx={{ minWidth: 200, mb: 2 }}>
        <InputLabel>Sprint</InputLabel>
        <Select value={sprintId} onChange={(e) => setSprintId(e.target.value as number)} label="Sprint">
          {sprints.map((s: any) => (
            <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>
          ))}
        </Select>
      </FormControl>

      {!sprintId && <Typography color="textSecondary">Selecciona un sprint</Typography>}
      {sprintId && isLoading && <CircularProgress />}
      {sprintId && data && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6">{data.sprint.name}</Typography>
          <Typography variant="body2" color="textSecondary">
            Total: {data.total_points} puntos / {data.total_tasks} tareas
          </Typography>
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2">Ideal vs Actual</Typography>
            <Box component="table" sx={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>Fecha</th>
                  <th style={{ borderBottom: "1px solid #eee" }}>Ideal</th>
                  <th style={{ borderBottom: "1px solid #eee" }}>Actual</th>
                </tr>
              </thead>
              <tbody>
                {data.ideal.map((ideal: any, i: number) => (
                  <tr key={i}>
                    <td>{ideal.date}</td>
                    <td style={{ textAlign: "center" }}>{ideal.ideal}</td>
                    <td style={{ textAlign: "center" }}>{data.actual[i]?.remaining ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </Box>
          </Box>
        </Paper>
      )}
    </Box>
  );
}
