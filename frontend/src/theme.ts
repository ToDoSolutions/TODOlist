import { createTheme, Theme } from "@mui/material/styles";

export function createAppTheme(dark: boolean): Theme {
  return createTheme({
    palette: {
      mode: dark ? "dark" : "light",
      primary: { main: "#1976d2" },
      secondary: { main: "#43a047" },
    },
    shape: { borderRadius: 10 },
    components: {
      MuiButton: { defaultProps: { disableElevation: true } },
    },
  });
}

export const theme = createAppTheme(false);
