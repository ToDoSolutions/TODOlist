import { useForm } from "react-hook-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
} from "@mui/material";
import { User as UserIcon } from "lucide-react";
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
    </Box>
  );
}
