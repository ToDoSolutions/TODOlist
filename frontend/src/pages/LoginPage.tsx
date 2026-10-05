import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Box,
  Button,
  Divider,
  Link,
  TextField,
  Typography,
  Alert,
  IconButton,
  InputAdornment,
  Fade,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import {
  Github,
  Mail,
  Lock,
  Eye,
  EyeOff,
  CheckCircle2,
  Zap,
  Calendar,
  BarChart3,
  KeyRound,
} from "lucide-react";
import { useNavigate, Link as RouterLink, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { notify } from "../notify";
import { githubApi, type ApiError } from "../api/resources";
import { apiErrorText } from "../lib/apiError";
import { ssoApi, type SsoProvider } from "../api/featEnt";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import "../i18n";

type FormValues = { email: string; password: string };

export default function LoginPage() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const [serverError, setServerError] = useState("");
  const [githubLoading, setGithubLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [needs2fa, setNeeds2fa] = useState(false);
  const [totpCode, setTotpCode] = useState("");
  const [providers, setProviders] = useState<{ github: boolean; google: boolean }>({
    github: false,
    google: false,
  });
  const [ssoProviders, setSsoProviders] = useState<SsoProvider[]>([]);

  useEffect(() => {
    githubApi
      .getProviders()
      .then(setProviders)
      .catch(() => {});
    // Endpoint público AllowAny; no fatal si no existe aún (404) — la
    // página funciona igual sin botones SSO enterprise.
    ssoApi
      .providers()
      .then(setSsoProviders)
      .catch(() => {});
  }, []);

  // Botones SSO enterprise: cada provider habilitado que no sea github (que
  // tiene su propio flujo OAuth) ni el google ya pintado por el bloque legacy.
  const ssoButtons = ssoProviders.filter(
    (p) => p.enabled && p.id !== "github" && !(p.id === "google" && providers.google),
  );

  const schema = z.object({
    email: z.string().email(t("p.auth.errors.emailInvalid")),
    password: z.string().min(1, t("p.auth.errors.required")),
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setServerError("");
    try {
      await login(values.email, values.password, needs2fa ? totpCode : undefined);
      notify.success(t("p.auth.login.success"));
      // Destino post-login: state.from (rutas protegidas) o ?next= (sesión expirada)
      const nextParam = new URLSearchParams(location.search).get("next");
      const dest =
        nextParam && nextParam.startsWith("/")
          ? nextParam
          : (location.state as { from?: string })?.from || "/app";
      navigate(dest);
    } catch (e) {
      // La cuenta tiene 2FA activo: pedir el código TOTP/backup
      const err = e as ApiError;
      if (err.response?.data?.requires_2fa) {
        setNeeds2fa(true);
        setServerError("");
        return;
      }
      const msg =
        err.response?.data?.totp_code ||
        apiErrorText(err, t, "p.auth.errors.loginFailed");
      setServerError(typeof msg === "string" ? msg : t("p.auth.errors.invalid2fa"));
      notify.error(typeof msg === "string" ? msg : t("p.auth.errors.invalid2fa"));
    }
  };

  const handleGitHubLogin = async () => {
    setGithubLoading(true);
    setServerError("");
    try {
      const { auth_url } = await githubApi.getOAuthUrl();
      window.location.href = auth_url;
    } catch (e) {
      const err = e as ApiError;
      const msg = apiErrorText(e, t, "p.auth.errors.githubConnect");
      setServerError(msg);
      notify.error(msg);
      setGithubLoading(false);
    }
  };

  const features = [
    { icon: CheckCircle2, text: t("p.auth.features.tasks") },
    { icon: Zap, text: t("p.auth.features.automations") },
    { icon: BarChart3, text: t("p.auth.features.dashboards") },
    { icon: Calendar, text: t("p.auth.features.sprints") },
  ];

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        bgcolor: "background.default",
      }}
    >
      {/* Panel izquierdo — Branding (solo desktop) */}
      {isDesktop && (
        <Box
          sx={{
            flex: "1 1 55%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            position: "relative",
            overflow: "hidden",
            background: (theme) =>
              `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 50%, #00BFA6 100%)`,
          }}
        >
          {/* Decorative shapes */}
          <Box
            component={motion.div}
            animate={{ rotate: 360 }}
            transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
            sx={{
              position: "absolute",
              top: "-15%",
              right: "-10%",
              width: 400,
              height: 400,
              borderRadius: "50%",
              background: "rgba(255,255,255,0.06)",
            }}
          />
          <Box
            component={motion.div}
            animate={{ y: [0, -20, 0] }}
            transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            sx={{
              position: "absolute",
              bottom: "10%",
              left: "5%",
              width: 120,
              height: 120,
              borderRadius: "30%",
              background: "rgba(255,255,255,0.08)",
            }}
          />

          <Box sx={{ position: "relative", zIndex: 1, px: 8, maxWidth: 600 }}>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
            >
              <Typography
                sx={{
                  color: "common.white",
                  fontSize: "2rem",
                  fontWeight: 800,
                  letterSpacing: "-0.02em",
                  mb: 3,
                }}
              >
                TODOlist
              </Typography>
              <Typography
                sx={{
                  color: "common.white",
                  fontSize: "2.5rem",
                  fontWeight: 700,
                  lineHeight: 1.2,
                  letterSpacing: "-0.02em",
                  mb: 2,
                }}
              >
                {t("p.auth.login.heroTitle1")}
                <br />
                {t("p.auth.login.heroTitle2")}
              </Typography>
              <Typography
                sx={{ color: "rgba(255,255,255,0.8)", fontSize: "1.125rem", mb: 5 }}
              >
                {t("p.auth.heroSubtitle")}
              </Typography>
            </motion.div>

            <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {features.map((f, i) => (
                <motion.div
                  key={f.text}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.5, delay: 0.3 + i * 0.1 }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <f.icon size={22} style={{ color: theme.palette.common.white }} />
                    <Typography sx={{ color: "rgba(255,255,255,0.9)", fontSize: "1rem" }}>
                      {f.text}
                    </Typography>
                  </Box>
                </motion.div>
              ))}
            </Box>
          </Box>
        </Box>
      )}

      {/* Panel derecho — Formulario */}
      <Box
        sx={{
          flex: "1 1 45%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          px: { xs: 3, sm: 6 },
          py: 4,
        }}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          style={{ width: "100%", maxWidth: 400 }}
        >
          {/* Logo móvil */}
          {!isDesktop && (
            <Typography
              sx={{ fontSize: "1.5rem", fontWeight: 800, mb: 3, color: "primary.main" }}
            >
              TODOlist
            </Typography>
          )}

          <Typography
            variant="h4"
            fontWeight={700}
            sx={{ mb: 1, letterSpacing: "-0.02em" }}
          >
            {t("p.auth.login.welcomeBack")}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
            {t("p.auth.login.subtitle")}
          </Typography>

          {serverError && (
            <Fade in={!!serverError}>
              <Alert severity="error" sx={{ mb: 3, borderRadius: 3 }}>
                {serverError}
              </Alert>
            </Fade>
          )}

          <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
            <TextField
              label={t("p.auth.email")}
              fullWidth
              margin="normal"
              autoComplete="email"
              autoFocus
              error={!!errors.email}
              helperText={errors.email?.message}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Mail size={18} color={theme.palette.text.secondary} />
                  </InputAdornment>
                ),
              }}
              {...register("email")}
            />
            <TextField
              label={t("p.auth.password")}
              type={showPassword ? "text" : "password"}
              fullWidth
              margin="normal"
              autoComplete="current-password"
              error={!!errors.password}
              helperText={errors.password?.message}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Lock size={18} color={theme.palette.text.secondary} />
                  </InputAdornment>
                ),
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPassword(!showPassword)}
                      edge="end"
                      size="small"
                      aria-label={t("p.auth.showPassword")}
                    >
                      {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
              {...register("password")}
            />

            {needs2fa && (
              <TextField
                label={t("p.auth.totpLabel")}
                fullWidth
                margin="normal"
                autoComplete="one-time-code"
                autoFocus
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.trim())}
                helperText={t("p.auth.totpHelper")}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Lock size={18} color={theme.palette.text.secondary} />
                    </InputAdornment>
                  ),
                }}
              />
            )}

            <Box textAlign="right" mt={0.5}>
              <Button
                component={RouterLink}
                to="/forgot-password"
                size="small"
                sx={{ textTransform: "none" }}
              >
                {t("p.auth.forgotPassword")}
              </Button>
            </Box>

            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              sx={{ mt: 2, mb: 2, py: 1.5, fontSize: "0.95rem" }}
              disabled={isSubmitting}
            >
              {isSubmitting ? t("p.auth.login.signingIn") : t("p.auth.login.submit")}
            </Button>
          </Box>

          {/* OAuth providers — solo si están configurados */}
          {(providers.github || providers.google || ssoButtons.length > 0) && (
            <>
              <Divider sx={{ my: 3 }}>
                <Typography variant="caption" color="text.secondary">
                  {t("p.auth.orContinueWith")}
                </Typography>
              </Divider>

              <Box sx={{ display: "flex", gap: 2 }}>
                {providers.github && (
                  <Button
                    fullWidth
                    variant="outlined"
                    size="large"
                    startIcon={<Github size={20} />}
                    onClick={handleGitHubLogin}
                    disabled={githubLoading}
                    sx={{ py: 1.5 }}
                  >
                    {githubLoading ? t("p.auth.connecting") : "GitHub"}
                  </Button>
                )}
                {providers.google && (
                  <Button
                    fullWidth
                    variant="outlined"
                    size="large"
                    startIcon={
                      <Box component="svg" width={20} height={20} viewBox="0 0 24 24">
                        <path
                          fill="#4285F4"
                          d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                        />
                        <path
                          fill="#34A853"
                          d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                        />
                        <path
                          fill="#FBBC05"
                          d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                        />
                        <path
                          fill="#EA4335"
                          d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                        />
                      </Box>
                    }
                    onClick={() => {
                      window.location.href = "/api/auth/social/login/google/";
                    }}
                    sx={{ py: 1.5 }}
                  >
                    Google
                  </Button>
                )}
              </Box>

              {/* SSO enterprise — redirección de página completa, no XHR */}
              {ssoButtons.length > 0 && (
                <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5, mt: 1.5 }}>
                  {ssoButtons.map((p) => (
                    <Button
                      key={p.id}
                      component="a"
                      href={p.login_url}
                      fullWidth
                      variant="outlined"
                      size="large"
                      startIcon={<KeyRound size={18} />}
                      sx={{ py: 1.5 }}
                    >
                      {p.name || t("p.ent.sso.fallback")}
                    </Button>
                  ))}
                </Box>
              )}
            </>
          )}

          <Typography variant="body2" mt={4} textAlign="center" color="text.secondary">
            {t("p.auth.noAccount")}{" "}
            <Link component={RouterLink} to="/register" fontWeight={600}>
              {t("p.auth.registerFree")}
            </Link>
          </Typography>

          {/* Demo credentials hint */}
          <Alert
            severity="info"
            sx={{
              mt: 3,
              borderRadius: 3,
              "& .MuiAlert-message": { fontSize: "0.8125rem" },
            }}
            icon={false}
          >
            <Typography variant="caption" color="text.secondary">
              <strong>{t("p.auth.demoAccount")}</strong> demo@todolist.com / demo12345
            </Typography>
          </Alert>
        </motion.div>
      </Box>
    </Box>
  );
}
