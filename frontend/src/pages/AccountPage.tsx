import { useNavigate } from "react-router-dom";
import {
  Box,
  GridLegacy as Grid,
  Paper,
  Typography,
  Stack,
  Divider,
  ToggleButton,
  ToggleButtonGroup,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Tooltip,
  useTheme,
} from "@mui/material";
import {
  User,
  Bell,
  Shield,
  Key,
  Smartphone,
  Download,
  AlertTriangle,
  Palette,
} from "lucide-react";
import PageHeader from "../components/ui/PageHeader";
import { useUiStore, type Density } from "../store/uiStore";
import { useThemeMode } from "../theme-context";
import { ACCENTS } from "../theme";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/AuthContext";
import "../i18n";

const SECTIONS = [
  {
    title: "p.misc.account.sectionProfile",
    desc: "p.misc.account.sectionProfileDesc",
    icon: <User size={22} />,
    path: "/app/profile",
  },
  {
    title: "nav.notifications",
    desc: "p.misc.account.sectionNotificationsDesc",
    icon: <Bell size={22} />,
    path: "/app/notifications",
  },
  {
    title: "nav.security",
    desc: "p.misc.account.sectionSecurityDesc",
    icon: <Shield size={22} />,
    path: "/app/security",
  },
  {
    title: "p.misc.account.sectionSessions",
    desc: "p.misc.account.sectionSessionsDesc",
    icon: <Smartphone size={22} />,
    path: "/app/offline-sync",
  },
  {
    title: "p.misc.account.sectionApiKeys",
    desc: "p.misc.account.sectionApiKeysDesc",
    icon: <Key size={22} />,
    path: "/app/api-keys",
  },
  {
    title: "p.misc.account.sectionExport",
    desc: "p.misc.account.sectionExportDesc",
    icon: <Download size={22} />,
    path: "/app/import-export",
  },
];

/**
 * Cuenta personal: preferencias del usuario (apariencia, idioma, densidad)
 * + acceso a perfil, seguridad y datos. Las funciones del workspace viven
 * en Administración, no aquí.
 */
export default function AccountPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { mode, toggle } = useThemeMode();
  const theme = useTheme();
  const density = useUiStore((s) => s.density);
  const setDensity = useUiStore((s) => s.setDensity);
  const accent = useUiStore((s) => s.accent);
  const setAccent = useUiStore((s) => s.setAccent);
  const { t, i18n } = useTranslation();
  const changeLang = (lang: string) => {
    i18n.changeLanguage(lang);
    localStorage.setItem("i18n-lang", lang);
  };

  return (
    <Box>
      <PageHeader
        title={t("p.misc.account.title")}
        description={user?.email ?? ""}
      />

      {/* Apariencia: ajustes inline, efecto inmediato */}
      <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
        <Stack direction="row" spacing={1.5} alignItems="center" mb={2}>
          <Palette size={18} />
          <Typography variant="subtitle1" fontWeight={700}>
            {t("p.misc.account.appearance")}
          </Typography>
        </Stack>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={3}
          flexWrap="wrap"
          useFlexGap
        >
          <Box>
            <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
              {t("p.misc.account.theme")}
            </Typography>
            <ToggleButtonGroup
              size="small"
              exclusive
              value={mode}
              onChange={() => toggle()}
            >
              <ToggleButton value="light">{t("p.misc.account.themeLight")}</ToggleButton>
              <ToggleButton value="dark">{t("p.misc.account.themeDark")}</ToggleButton>
            </ToggleButtonGroup>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
              {t("p.misc.account.density")}
            </Typography>
            <ToggleButtonGroup
              size="small"
              exclusive
              value={density}
              onChange={(_, v: Density | null) => v && setDensity(v)}
            >
              <ToggleButton value="comfortable">
                {t("p.misc.account.densityComfortable")}
              </ToggleButton>
              <ToggleButton value="standard">
                {t("p.misc.account.densityStandard")}
              </ToggleButton>
              <ToggleButton value="compact">
                {t("p.misc.account.densityCompact")}
              </ToggleButton>
            </ToggleButtonGroup>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
              {t("p.misc.appearance.accent.label")}
            </Typography>
            <Stack
              direction="row"
              spacing={1}
              role="radiogroup"
              aria-label={t("p.misc.appearance.accent.label")}
            >
              {Object.entries(ACCENTS).map(([key, a]) => {
                const selected = accent === key;
                const name = t(`p.misc.appearance.accent.${key}`);
                return (
                  <Tooltip key={key} title={name} arrow>
                    <Box
                      component="button"
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      aria-label={name}
                      onClick={() => setAccent(key)}
                      sx={{
                        width: 28,
                        height: 28,
                        borderRadius: "50%",
                        p: 0,
                        cursor: "pointer",
                        border: `1px solid ${theme.palette.divider}`,
                        background: `linear-gradient(135deg, ${a.primary.main} 50%, ${a.secondary.main} 50%)`,
                        boxShadow: selected
                          ? `0 0 0 2px ${theme.palette.background.paper}, 0 0 0 4px ${a.primary.main}`
                          : "none",
                        transition: "box-shadow 0.15s ease",
                        "&:hover": {
                          boxShadow: `0 0 0 2px ${theme.palette.background.paper}, 0 0 0 4px ${a.primary.light}`,
                        },
                      }}
                    />
                  </Tooltip>
                );
              })}
            </Stack>
          </Box>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>{t("p.misc.language")}</InputLabel>
            <Select
              label={t("p.misc.language")}
              value={i18n.language}
              onChange={(e) => changeLang(e.target.value)}
            >
              <MenuItem value="es">Español</MenuItem>
              <MenuItem value="en">English</MenuItem>
            </Select>
          </FormControl>
        </Stack>
      </Paper>

      <Grid container spacing={2}>
        {SECTIONS.map((s) => (
          <Grid item xs={12} sm={6} md={4} key={s.path}>
            <Paper
              variant="outlined"
              sx={{
                p: 2,
                cursor: "pointer",
                "&:hover": { borderColor: "primary.main" },
                height: "100%",
              }}
              onClick={() => navigate(s.path)}
              role="link"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && navigate(s.path)}
            >
              <Stack direction="row" spacing={1.5} alignItems="flex-start">
                <Box color="primary.main" mt={0.25}>
                  {s.icon}
                </Box>
                <Box>
                  <Typography variant="subtitle2" fontWeight={700}>
                    {t(s.title)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {t(s.desc)}
                  </Typography>
                </Box>
              </Stack>
            </Paper>
          </Grid>
        ))}
      </Grid>

      <Divider sx={{ my: 3 }} />
      <Paper
        variant="outlined"
        sx={{ p: 2, borderColor: "error.light", cursor: "pointer" }}
        onClick={() => navigate("/app/profile")}
        role="link"
        tabIndex={0}
      >
        <Stack direction="row" spacing={1.5} alignItems="center">
          <AlertTriangle size={18} color="#d32f2f" />
          <Box>
            <Typography variant="subtitle2" fontWeight={700} color="error.main">
              {t("p.misc.dangerZone")}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t("p.misc.account.dangerDesc")}
            </Typography>
          </Box>
        </Stack>
      </Paper>
    </Box>
  );
}
