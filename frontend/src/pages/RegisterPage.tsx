import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Box,
  Button,
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
  User,
  Mail,
  Lock,
  Eye,
  EyeOff,
  CheckCircle2,
  Zap,
  BarChart3,
  Calendar,
} from "lucide-react";
import { useNavigate, Link as RouterLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import type { ApiError } from "../api/resources";
import { notify } from "../notify";
import { useState } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import "../i18n";

type FormValues = {
  username: string;
  email: string;
  password: string;
  password2: string;
};

export default function RegisterPage() {
  const { t } = useTranslation();
  const { register: registerUser } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const [serverError, setServerError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showPassword2, setShowPassword2] = useState(false);

  const schema = z
    .object({
      username: z.string().min(3, t("p.auth.errors.minChars", { count: 3 })),
      email: z.string().email(t("p.auth.errors.emailInvalid")),
      password: z.string().min(8, t("p.auth.errors.minChars", { count: 8 })),
      password2: z.string().min(8, t("p.auth.errors.minChars", { count: 8 })),
    })
    .refine((d) => d.password === d.password2, {
      path: ["password2"],
      message: t("p.auth.errors.passwordsMismatch"),
    });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setServerError("");
    try {
      await registerUser(values.email, values.username, values.password);
      notify.success(t("p.auth.register.success"));
      navigate("/app");
    } catch (e) {
      const data = (e as ApiError).response?.data;
      const msg =
        typeof data === "string"
          ? data
          : (data?.email as string[] | undefined)?.[0] ||
            (data?.username as string[] | undefined)?.[0] ||
            t("p.auth.errors.registerFailed");
      setServerError(msg);
      notify.error(msg);
    }
  };

  const features = [
    { icon: CheckCircle2, text: t("p.auth.features.tasks") },
    { icon: Zap, text: t("p.auth.features.automations") },
    { icon: BarChart3, text: t("p.auth.features.dashboards") },
    { icon: Calendar, text: t("p.auth.features.sprints") },
  ];

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", bgcolor: "background.default" }}>
      {/* Panel izquierdo — Branding */}
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
              `linear-gradient(135deg, #00BFA6 0%, ${theme.palette.primary.main} 50%, ${theme.palette.primary.dark} 100%)`,
          }}
        >
          <Box
            component={motion.div}
            animate={{ rotate: -360 }}
            transition={{ duration: 80, repeat: Infinity, ease: "linear" }}
            sx={{
              position: "absolute",
              bottom: "-15%",
              left: "-10%",
              width: 350,
              height: 350,
              borderRadius: "50%",
              background: "rgba(255,255,255,0.06)",
            }}
          />
          <Box
            component={motion.div}
            animate={{ y: [0, 20, 0] }}
            transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
            sx={{
              position: "absolute",
              top: "15%",
              right: "8%",
              width: 100,
              height: 100,
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
                sx={{ color: "common.white", fontSize: "2rem", fontWeight: 800, mb: 3 }}
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
                {t("p.auth.register.heroTitle1")}
                <br />
                {t("p.auth.register.heroTitle2")}
              </Typography>
              <Typography
                sx={{ color: "rgba(255,255,255,0.8)", fontSize: "1.125rem", mb: 5 }}
              >
                {t("p.auth.register.heroSubtitle")}
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
            {t("p.auth.register.title")}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
            {t("p.auth.register.subtitle")}
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
              label={t("p.auth.username")}
              fullWidth
              margin="normal"
              autoComplete="username"
              autoFocus
              error={!!errors.username}
              helperText={errors.username?.message}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <User size={18} color={theme.palette.text.secondary} />
                  </InputAdornment>
                ),
              }}
              {...register("username")}
            />
            <TextField
              label={t("p.auth.email")}
              fullWidth
              margin="normal"
              autoComplete="email"
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
              autoComplete="new-password"
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
            <TextField
              label={t("p.auth.confirmPassword")}
              type={showPassword2 ? "text" : "password"}
              fullWidth
              margin="normal"
              autoComplete="new-password"
              error={!!errors.password2}
              helperText={errors.password2?.message}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Lock size={18} color={theme.palette.text.secondary} />
                  </InputAdornment>
                ),
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPassword2(!showPassword2)}
                      edge="end"
                      size="small"
                      aria-label={t("p.auth.showPassword")}
                    >
                      {showPassword2 ? <EyeOff size={18} /> : <Eye size={18} />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
              {...register("password2")}
            />

            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              sx={{ mt: 3, mb: 2, py: 1.5, fontSize: "0.95rem" }}
              disabled={isSubmitting}
            >
              {isSubmitting ? t("p.auth.register.creating") : t("p.auth.register.submit")}
            </Button>
          </Box>

          <Typography variant="body2" mt={4} textAlign="center" color="text.secondary">
            {t("p.auth.haveAccount")}{" "}
            <Link component={RouterLink} to="/login" fontWeight={600}>
              {t("p.auth.signInLink")}
            </Link>
          </Typography>
        </motion.div>
      </Box>
    </Box>
  );
}
