import { useForm } from "react-hook-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  Box,
  Typography,
  Button,
  TextField,
  MenuItem,
  Card,
  CardContent,
  Stack,
  Avatar,
  Alert,
  Divider,
  IconButton,
  InputAdornment,
} from "@mui/material";
import { User as UserIcon, Lock, Eye, EyeOff } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { authApi } from "../api/auth";
import { notify } from "../notify";

interface FormValues {
  username: string;
  timezone: string;
  locale: string;
}

const LOCALES = [
  { value: "es", label: "Español" },
  { value: "en", label: "English" },
  { value: "fr", label: "Français" },
  { value: "de", label: "Deutsch" },
  { value: "it", label: "Italiano" },
  { value: "pt", label: "Português" },
];

const TIMEZONES = ["UTC", "Europe/Madrid", "Europe/London", "America/New_York", "America/Mexico_City", "Asia/Tokyo"];

export default function ProfilePage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [pwForm, setPwForm] = useState({ current_password: "", new_password: "", confirm: "" });
  const [pwError, setPwError] = useState("");

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    defaultValues: {
      username: user?.username || "",
      timezone: user?.timezone || "UTC",
      locale: user?.locale || "es",
    },
  });

  const save = useMutation({
    mutationFn: (v: FormValues) => authApi.updateMe(v),
    onSuccess: () => {
      notify.success("Perfil actualizado");
      qc.invalidateQueries({ queryKey: ["me"] });
    },
    onError: () => notify.error("No se pudo actualizar el perfil"),
  });

  const changePw = useMutation({
    mutationFn: () => authApi.changePassword(pwForm.current_password, pwForm.new_password),
    onSuccess: () => {
      notify.success("Contraseña actualizada");
      setPwForm({ current_password: "", new_password: "", confirm: "" });
      setPwError("");
    },
    onError: (e: any) => {
      const msg = e.response?.data?.error || "No se pudo cambiar la contraseña.";
      setPwError(msg);
      notify.error(msg);
    },
  });

  const submitPassword = () => {
    setPwError("");
    if (!pwForm.current_password || !pwForm.new_password) {
      setPwError("Completa todos los campos.");
      return;
    }
    if (pwForm.new_password.length < 8) {
      setPwError("La nueva contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (pwForm.new_password !== pwForm.confirm) {
      setPwError("Las contraseñas no coinciden.");
      return;
    }
    changePw.mutate();
  };

  return (
    <Box sx={{ maxWidth: 600 }}>
      <Typography variant="h5" fontWeight={700} mb={3}>
        Mi perfil
      </Typography>
      <Card>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" spacing={2} alignItems="center" mb={3}>
            <Avatar sx={{ width: 64, height: 64, bgcolor: "primary.main", fontSize: 28 }}>
              {user?.email?.[0]?.toUpperCase() || <UserIcon size={28} />}
            </Avatar>
            <Box>
              <Typography variant="subtitle1" fontWeight={600}>
                {user?.email}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                ID: {user?.id}
              </Typography>
            </Box>
          </Stack>

          <Box component="form" onSubmit={handleSubmit((v) => save.mutate(v))}>
            <Stack spacing={2}>
              <TextField
                label="Nombre de usuario"
                fullWidth
                error={!!errors.username}
                helperText={errors.username?.message}
                {...register("username", { required: "Requerido", minLength: 3 })}
              />
              <TextField
                label="Email"
                fullWidth
                value={user?.email || ""}
                disabled
                helperText="El email no se puede cambiar"
              />
              <TextField select label="Idioma" fullWidth {...register("locale")}>
                {LOCALES.map((l) => (
                  <MenuItem key={l.value} value={l.value}>
                    {l.label}
                  </MenuItem>
                ))}
              </TextField>
              <TextField select label="Zona horaria" fullWidth {...register("timezone")}>
                {TIMEZONES.map((tz) => (
                  <MenuItem key={tz} value={tz}>
                    {tz}
                  </MenuItem>
                ))}
              </TextField>
              <Button type="submit" variant="contained" disabled={save.isPending}>
                Guardar cambios
              </Button>
            </Stack>
          </Box>
        </CardContent>
      </Card>

      {/* Cambiar contraseña */}
      <Card sx={{ mt: 3 }}>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center" mb={2}>
            <Lock size={20} color="primary.main" />
            <Typography variant="h6" fontWeight={600}>Cambiar contraseña</Typography>
          </Stack>
          <Divider sx={{ mb: 2 }} />
          {pwError && <Alert severity="error" sx={{ mb: 2 }}>{pwError}</Alert>}
          <Stack spacing={2}>
            <TextField
              label="Contraseña actual"
              type={showCurrent ? "text" : "password"}
              fullWidth
              autoComplete="current-password"
              value={pwForm.current_password}
              onChange={(e) => setPwForm({ ...pwForm, current_password: e.target.value })}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={() => setShowCurrent(!showCurrent)}>
                      {showCurrent ? <EyeOff size={18} /> : <Eye size={18} />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              label="Nueva contraseña"
              type={showNew ? "text" : "password"}
              fullWidth
              autoComplete="new-password"
              value={pwForm.new_password}
              onChange={(e) => setPwForm({ ...pwForm, new_password: e.target.value })}
              helperText="Mínimo 8 caracteres"
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={() => setShowNew(!showNew)}>
                      {showNew ? <EyeOff size={18} /> : <Eye size={18} />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              label="Repetir nueva contraseña"
              type={showNew ? "text" : "password"}
              fullWidth
              autoComplete="new-password"
              value={pwForm.confirm}
              onChange={(e) => setPwForm({ ...pwForm, confirm: e.target.value })}
            />
            <Button variant="contained" disabled={changePw.isPending} onClick={submitPassword}>
              {changePw.isPending ? "Guardando..." : "Cambiar contraseña"}
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
