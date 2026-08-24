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
import { useNavigate, Link as RouterLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { notify } from "../notify";
import { useState } from "react";

const schema = z
  .object({
    username: z.string().min(3, "Mínimo 3 caracteres"),
    email: z.string().email("Email no válido"),
    password: z.string().min(8, "Mínimo 8 caracteres"),
    password2: z.string().min(8, "Mínimo 8 caracteres"),
  })
  .refine((d) => d.password === d.password2, {
    path: ["password2"],
    message: "Las contraseñas no coinciden",
  });

type FormValues = z.infer<typeof schema>;

export default function RegisterPage() {
  const { register: registerUser } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState("");

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setServerError("");
    try {
      await registerUser(values.email, values.username, values.password);
      notify.success("Cuenta creada");
      navigate("/app");
    } catch (e: any) {
      const data = e.response?.data;
      const msg =
        typeof data === "string"
          ? data
          : data?.email?.[0] || data?.username?.[0] || "No se pudo registrar.";
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
            Crear cuenta
          </Typography>
          {serverError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {serverError}
            </Alert>
          )}
          <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
            <TextField
              label="Nombre de usuario"
              fullWidth
              margin="normal"
              error={!!errors.username}
              helperText={errors.username?.message}
              {...register("username")}
            />
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
              error={!!errors.password}
              helperText={errors.password?.message}
              {...register("password")}
            />
            <TextField
              label="Repetir contraseña"
              type="password"
              fullWidth
              margin="normal"
              error={!!errors.password2}
              helperText={errors.password2?.message}
              {...register("password2")}
            />
            <Button
              type="submit"
              fullWidth
              variant="contained"
              sx={{ mt: 2 }}
              disabled={isSubmitting}
            >
              Registrarme
            </Button>
          </Box>
          <Typography variant="body2" mt={2} textAlign="center">
            ¿Ya tienes cuenta?{" "}
            <Link component={RouterLink} to="/login">
              Inicia sesión
            </Link>
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
