import { createTheme, Theme, Shadows } from "@mui/material/styles";

// Material 3 color scheme — roles semánticos
const lightPalette = {
  primary: { main: "#5B7CFA", light: "#7B97FF", dark: "#3D5BD9", contrastText: "#FFFFFF" },
  secondary: { main: "#FF6B9D", light: "#FF8FB5", dark: "#E04B7D", contrastText: "#FFFFFF" },
  tertiary: { main: "#00BFA6", light: "#2DD4BF", dark: "#00897B", contrastText: "#FFFFFF" },
  error: { main: "#F44336", light: "#FF7961", dark: "#BA000D", contrastText: "#FFFFFF" },
  warning: { main: "#FF9800", light: "#FFB74D", dark: "#F57C00" },
  info: { main: "#29B6F6", light: "#4FC3F7", dark: "#0288D1" },
  success: { main: "#66BB6A", light: "#81C784", dark: "#43A047" },
  background: {
    default: "#F7F8FC",
    paper: "#FFFFFF",
  },
  text: {
    primary: "#1A1B2E",
    secondary: "#6B7280",
    disabled: "#9CA3AF",
  },
  divider: "rgba(0,0,0,0.08)",
  // M3 extended roles
  primaryContainer: { main: "#E0E7FF", contrastText: "#1A237E" },
  secondaryContainer: { main: "#FCE4EC", contrastText: "#880E4F" },
  tertiaryContainer: { main: "#E0F7FA", contrastText: "#004D40" },
  errorContainer: { main: "#FFEBEE", contrastText: "#B71C1C" },
  surfaceVariant: { main: "#EEF0F6" },
  surfaceContainer: { main: "#F0F2F8" },
  surfaceContainerHigh: { main: "#E8EAF0" },
  surfaceContainerHighest: { main: "#E2E5EC" },
  outline: { main: "#B0BAC8" },
  outlineVariant: { main: "#D4DAE6" },
  scrim: { main: "rgba(0,0,0,0.5)" },
};

const darkPalette = {
  primary: { main: "#7B97FF", light: "#9DB0FF", dark: "#5B7CFA", contrastText: "#0A0E27" },
  secondary: { main: "#FF8FB5", light: "#FFB0CC", dark: "#FF6B9D", contrastText: "#0A0E27" },
  tertiary: { main: "#2DD4BF", light: "#5EEAD4", dark: "#00BFA6", contrastText: "#0A0E27" },
  error: { main: "#FF7961", light: "#FF9E8A", dark: "#F44336", contrastText: "#0A0E27" },
  warning: { main: "#FFB74D", light: "#FFCC80", dark: "#FF9800" },
  info: { main: "#4FC3F7", light: "#80D4F9", dark: "#29B6F6" },
  success: { main: "#81C784", light: "#A5D6A7", dark: "#66BB6A" },
  background: {
    default: "#0A0E27",
    paper: "#131830",
  },
  text: {
    primary: "#F1F3F9",
    secondary: "#9CA8C7",
    disabled: "#5C6680",
  },
  divider: "rgba(255,255,255,0.08)",
  // M3 extended roles — tonal surfaces for dark mode
  primaryContainer: { main: "#1A237E", contrastText: "#C5CAE9" },
  secondaryContainer: { main: "#880E4F", contrastText: "#F8BBD0" },
  tertiaryContainer: { main: "#004D40", contrastText: "#B2DFDB" },
  errorContainer: { main: "#B71C1C", contrastText: "#FFCDD2" },
  surfaceVariant: { main: "#1B213E" },
  surfaceContainer: { main: "#161B38" },
  surfaceContainerHigh: { main: "#1F2545" },
  surfaceContainerHighest: { main: "#262C4A" },
  outline: { main: "#5C6680" },
  outlineVariant: { main: "#2A3050" },
  scrim: { main: "rgba(0,0,0,0.6)" },
};

// Tipografía M3
const typography = {
  fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
  displayLarge: { fontSize: "3.5rem", fontWeight: 700, lineHeight: 1.1, letterSpacing: "-0.02em" },
  displayMedium: { fontSize: "2.75rem", fontWeight: 700, lineHeight: 1.15, letterSpacing: "-0.02em" },
  displaySmall: { fontSize: "2.25rem", fontWeight: 600, lineHeight: 1.2, letterSpacing: "-0.01em" },
  h1: { fontSize: "2.5rem", fontWeight: 700, lineHeight: 1.2, letterSpacing: "-0.02em" },
  h2: { fontSize: "2rem", fontWeight: 600, lineHeight: 1.25, letterSpacing: "-0.01em" },
  h3: { fontSize: "1.75rem", fontWeight: 600, lineHeight: 1.3 },
  h4: { fontSize: "1.5rem", fontWeight: 600, lineHeight: 1.35 },
  h5: { fontSize: "1.25rem", fontWeight: 600, lineHeight: 1.4 },
  h6: { fontSize: "1.125rem", fontWeight: 600, lineHeight: 1.5 },
  body1: { fontSize: "0.9375rem", lineHeight: 1.6, fontWeight: 400 },
  body2: { fontSize: "0.8125rem", lineHeight: 1.55, fontWeight: 400 },
  subtitle1: { fontSize: "1rem", fontWeight: 500, lineHeight: 1.5 },
  subtitle2: { fontSize: "0.875rem", fontWeight: 500, lineHeight: 1.5 },
  caption: { fontSize: "0.75rem", lineHeight: 1.4, fontWeight: 400 },
  overline: { fontSize: "0.6875rem", fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase" },
  button: { fontSize: "0.875rem", fontWeight: 600, letterSpacing: "0.01em", textTransform: "none" },
};

export function createAppTheme(dark: boolean): Theme {
  const palette = dark ? darkPalette : lightPalette;
  return createTheme({
    palette: {
      mode: dark ? "dark" : "light",
      ...palette,
    } as any,
    typography: typography as any,
    shape: { borderRadius: 12 },
    shadows: [
      "none",
      "0 1px 2px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.06)",
      "0 2px 4px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.06)",
      "0 4px 8px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.08)",
      "0 4px 12px rgba(0,0,0,0.05), 0 6px 16px rgba(0,0,0,0.08)",
      "0 6px 16px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.10)",
      "0 8px 24px rgba(0,0,0,0.08), 0 12px 32px rgba(0,0,0,0.12)",
      "0 8px 24px rgba(0,0,0,0.10), 0 12px 32px rgba(0,0,0,0.14)",
      "0 10px 30px rgba(0,0,0,0.12), 0 14px 40px rgba(0,0,0,0.16)",
      "0 12px 36px rgba(0,0,0,0.14), 0 16px 48px rgba(0,0,0,0.18)",
      "0 14px 40px rgba(0,0,0,0.16), 0 18px 56px rgba(0,0,0,0.20)",
      "0 16px 48px rgba(0,0,0,0.18), 0 20px 64px rgba(0,0,0,0.22)",
      "0 18px 56px rgba(0,0,0,0.20), 0 24px 72px rgba(0,0,0,0.24)",
      "0 20px 64px rgba(0,0,0,0.22), 0 28px 80px rgba(0,0,0,0.26)",
      "0 22px 72px rgba(0,0,0,0.24), 0 32px 88px rgba(0,0,0,0.28)",
      "0 24px 80px rgba(0,0,0,0.26), 0 36px 96px rgba(0,0,0,0.30)",
      "0 26px 88px rgba(0,0,0,0.28), 0 40px 104px rgba(0,0,0,0.32)",
      "0 28px 96px rgba(0,0,0,0.30), 0 44px 112px rgba(0,0,0,0.34)",
      "0 30px 104px rgba(0,0,0,0.32), 0 48px 120px rgba(0,0,0,0.36)",
      "0 32px 112px rgba(0,0,0,0.34), 0 52px 128px rgba(0,0,0,0.38)",
      "0 34px 120px rgba(0,0,0,0.36), 0 56px 136px rgba(0,0,0,0.40)",
      "0 36px 128px rgba(0,0,0,0.38), 0 60px 144px rgba(0,0,0,0.42)",
      "0 38px 136px rgba(0,0,0,0.40), 0 64px 152px rgba(0,0,0,0.44)",
      "0 40px 144px rgba(0,0,0,0.42), 0 68px 160px rgba(0,0,0,0.46)",
    ] as unknown as Shadows,
    transitions: {
      duration: {
        shortest: 150,
        shorter: 200,
        short: 250,
        standard: 300,
        complex: 375,
        enteringScreen: 225,
        leavingScreen: 195,
      },
      easing: {
        easeInOut: "cubic-bezier(0.4, 0, 0.2, 1)",
        easeOut: "cubic-bezier(0.0, 0, 0.2, 1)",
        easeIn: "cubic-bezier(0.4, 0, 1, 1)",
        sharp: "cubic-bezier(0.4, 0, 0.6, 1)",
      },
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          // Foco visible accesible — WCAG 2.2
          ":focus-visible": {
            outline: `2px solid ${dark ? "#7B97FF" : "#3D5BD9"}`,
            outlineOffset: 2,
          },
          // Respetar preferencia de reducción de movimiento
          "@media (prefers-reduced-motion: reduce)": {
            "*": {
              animationDuration: "0.01ms !important",
              animationIterationCount: "1 !important",
              transitionDuration: "0.01ms !important",
              scrollBehavior: "auto !important",
            },
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: {
            borderRadius: 10,
            paddingInline: 20,
            paddingBlock: 10,
            minHeight: 40,
            transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
          },
          contained: {
            "&:hover": { transform: "translateY(-1px)" },
          },
          outlined: {
            borderWidth: 1.5,
            "&:hover": { borderWidth: 1.5 },
          },
        },
      },
      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            borderRadius: 16,
            border: `1px solid ${dark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)"}`,
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          rounded: { borderRadius: 16 },
        },
      },
      MuiTextField: {
        defaultProps: {
          variant: "outlined",
        },
        styleOverrides: {
          root: {
            "& .MuiOutlinedInput-root": {
              borderRadius: 10,
              transition: "all 0.2s ease",
            },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: { borderRadius: 8, fontWeight: 500 },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            // Touch target mínimo 44x44 para accesibilidad móvil
            minHeight: 40,
            minWidth: 40,
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            backdropFilter: "blur(12px)",
            backgroundColor: dark ? "rgba(19,24,48,0.85)" : "rgba(255,255,255,0.85)",
            borderBottom: `1px solid ${dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)"}`,
          },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: {
            borderRight: `1px solid ${dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)"}`,
          },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderRadius: 10,
            marginInline: 8,
            marginBlock: 2,
            transition: "all 0.15s ease",
            "&.Mui-selected": {
              fontWeight: 600,
            },
          },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            borderRadius: 8,
            fontSize: "0.75rem",
            padding: "6px 10px",
          },
        },
      },
      MuiAlert: {
        styleOverrides: {
          root: { borderRadius: 12 },
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: { borderRadius: 20 },
        },
      },
      MuiLinearProgress: {
        styleOverrides: {
          root: { borderRadius: 999 },
        },
      },
      MuiCircularProgress: {
        defaultProps: { thickness: 4 },
      },
    },
  });
}

export const theme = createAppTheme(false);
