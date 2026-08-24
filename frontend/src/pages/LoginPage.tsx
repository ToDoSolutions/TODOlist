import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Box,
  Button,
  Card,
  CardContent,
  Link,
  TextField,
  Typography,
  Alert,
} from "@mui/material";
import { useNavigate, Link as RouterLink, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { notify } from "../notify";
import { useState } from "react";

const schema = z.object({
  email: z.string().email("Email no válido"),
  password: z.string().min(1, "Requerido"),
});

type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [serverError, setServerError] = useState("");

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
      const msg = e.response?.data?.detail || "No se pudo iniciar sesión.";
      setServerError(msg);
      notify.error(msg);
    }
  };

  return (
    <Box
      display="flex"
      minHeight="100vh"
      alignItems="center"
      justifyContent="center"
      sx={{ bgcolor: "background.default" }}
    >
      <Card sx={{ maxWidth: 420, width: "100%", mx: 2 }}>
        <CardContent sx={{ p: 4 }}>
          <Typography variant="h5" mb={2} fontWeight={700}>
            Iniciar sesión
          </Typography>
          {serverError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {serverError}
            </Alert>
          )}
          <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
            <TextField
              label="Email"
              fullWidth
              margin="normal"
              autoComplete="email"
              error={!!errors.email}
              helperText={errors.email?.message}
              {...register("email")}
            />
            <TextField
              label="Contraseña"
              type="password"
              fullWidth
              margin="normal"
              autoComplete="current-password"
              error={!!errors.password}
              helperText={errors.password?.message}
              {...register("password")}
            />
            <Button
              type="submit"
              fullWidth
              variant="contained"
              sx={{ mt: 2 }}
              disabled={isSubmitting}
            >
              Entrar
            </Button>
          </Box>
          <Typography variant="body2" mt={2} textAlign="center">
            ¿No tienes cuenta?{" "}
            <Link component={RouterLink} to="/register">
              Regístrate
            </Link>
          </Typography>
          <Alert severity="info" sx={{ mt: 2 }} icon={false}>
            Demo: demo@todolist.local / demo12345
          </Alert>
        </CardContent>
      </Card>
    </Box>
  );
}
