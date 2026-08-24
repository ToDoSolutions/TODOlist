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
} from "lucide-react";
import { useNavigate, Link as RouterLink, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { notify } from "../notify";
import { githubApi } from "../api/resources";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";

const schema = z.object({
  email: z.string().email("Email no válido"),
  password: z.string().min(1, "Requerido"),
});

type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const [serverError, setServerError] = useState("");
  const [githubLoading, setGithubLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [providers, setProviders] = useState<{ github: boolean; google: boolean }>({
    github: false,
    google: false,
  });

  useEffect(() => {
    githubApi
      .getProviders()
      .then(setProviders)
      .catch(() => {});
  }, []);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setServerError("");
    try {
      await login(values.email, values.password);
      notify.success("Sesión iniciada");
      const dest = (location.state as { from?: string })?.from || "/app";
      navigate(dest);
    } catch (e: any) {
      const msg = e.response?.data?.detail || "No se pudo iniciar sesión. Revisa tus credenciales.";
      setServerError(msg);
      notify.error(msg);
    }
  };

  const handleGitHubLogin = async () => {
    setGithubLoading(true);
    setServerError("");
    try {
      const { auth_url } = await githubApi.getOAuthUrl();
      window.location.href = auth_url;
    } catch (e: any) {
      const msg = e.response?.data?.error || "No se pudo conectar con GitHub.";
      setServerError(msg);
      notify.error(msg);
      setGithubLoading(false);
    }
  };

  const features = [
    { icon: CheckCircle2, text: "Gestión de tareas y proyectos" },
    { icon: Zap, text: "Automatizaciones y reglas" },
    { icon: BarChart3, text: "Dashboards y métricas" },
    { icon: Calendar, text: "Sprints, épicas y Gantt" },
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
                  color: "#fff",
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
                  color: "#fff",
                  fontSize: "2.5rem",
                  fontWeight: 700,
                  lineHeight: 1.2,
                  letterSpacing: "-0.02em",
                  mb: 2,
                }}
              >
                Organiza tu trabajo.
                <br />
                Impulsa tu productividad.
              </Typography>
              <Typography sx={{ color: "rgba(255,255,255,0.8)", fontSize: "1.125rem", mb: 5 }}>
                La plataforma todo-en-uno para gestionar tareas, sprints, equipos y proyectos.
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
                    <f.icon size={22} color="#fff" />
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
            <Typography sx={{ fontSize: "1.5rem", fontWeight: 800, mb: 3, color: "primary.main" }}>
              TODOlist
            </Typography>
          )}

          <Typography variant="h4" fontWeight={700} sx={{ mb: 1, letterSpacing: "-0.02em" }}>
            Bienvenido de nuevo
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
            Inicia sesión para continuar a tu espacio de trabajo
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
              label="Email"
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
              label="Contraseña"
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
                      aria-label="mostrar contraseña"
                    >
                      {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
              {...register("password")}
            />

            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              sx={{ mt: 3, mb: 2, py: 1.5, fontSize: "0.95rem" }}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Iniciando sesión..." : "Iniciar sesión"}
            </Button>
          </Box>

          {/* OAuth providers — solo si están configurados */}
          {(providers.github || providers.google) && (
            <>
              <Divider sx={{ my: 3 }}>
                <Typography variant="caption" color="text.secondary">
                  o continúa con
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
                    {githubLoading ? "Conectando..." : "GitHub"}
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
            </>
          )}

          <Typography variant="body2" mt={4} textAlign="center" color="text.secondary">
            ¿No tienes cuenta?{" "}
            <Link component={RouterLink} to="/register" fontWeight={600}>
              Regístrate gratis
            </Link>
          </Typography>

          {/* Demo credentials hint */}
          <Alert
            severity="info"
            sx={{ mt: 3, borderRadius: 3, "& .MuiAlert-message": { fontSize: "0.8125rem" } }}
            icon={false}
          >
            <Typography variant="caption" color="text.secondary">
              <strong>Cuenta demo:</strong> demo@todolist.local / demo12345
            </Typography>
          </Alert>
        </motion.div>
      </Box>
    </Box>
  );
}
