import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Typography,
  Button,
  Paper,
  Stack,
  Chip,
  IconButton,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Alert,
} from "@mui/material";
import { Plus, Trash2, Pencil, Tag as TagIcon } from "lucide-react";
import { tagsApi } from "../api/resources";
import { Tag } from "../types";
import { notify } from "../notify";

export default function TagsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Tag | null>(null);
  const [name, setName] = useState("");
  const [color, setColor] = useState("#1976d2");

  const { data: tags = [], isLoading } = useQuery({
    queryKey: ["tags"],
    queryFn: tagsApi.list,
  });

  const createMut = useMutation({
    mutationFn: () => tagsApi.create({ name: name.trim(), color }),
    onSuccess: () => {
      notify.success("Etiqueta creada");
      qc.invalidateQueries({ queryKey: ["tags"] });
      setOpen(false);
    },
    onError: () => notify.error("No se pudo crear la etiqueta"),
  });

  const updateMut = useMutation({
    mutationFn: () => tagsApi.update(editing!.id, { name: name.trim(), color }),
    onSuccess: () => {
      notify.success("Etiqueta actualizada");
      qc.invalidateQueries({ queryKey: ["tags"] });
      setOpen(false);
    },
    onError: () => notify.error("No se pudo actualizar"),
  });

  const removeMut = useMutation({
    mutationFn: (id: number) => tagsApi.remove(id),
    onSuccess: () => {
      notify.success("Etiqueta eliminada");
      qc.invalidateQueries({ queryKey: ["tags"] });
    },
    onError: () => notify.error("No se pudo eliminar"),
  });

  const openNew = () => {
    setEditing(null);
    setName("");
    setColor("#1976d2");
    setOpen(true);
  };

  const openEdit = (t: Tag) => {
    setEditing(t);
    setName(t.name);
    setColor(t.color);
    setOpen(true);
  };

  const save = () => {
    if (!name.trim()) return;
    if (editing) updateMut.mutate();
    else createMut.mutate();
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
        <Typography variant="h5" fontWeight={700}>
          Etiquetas
        </Typography>
        <Button variant="contained" startIcon={<Plus size={18} />} onClick={openNew}>
          Nueva etiqueta
        </Button>
      </Stack>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      ) : tags.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <TagIcon size={32} style={{ color: "#bbb" }} />
          <Typography color="text.secondary" mt={1}>
            No hay etiquetas. Crea la primera para organizar tus tareas.
          </Typography>
        </Paper>
      ) : (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {tags.map((t) => (
              <Chip
                key={t.id}
                label={t.name}
                sx={{ bgcolor: t.color, color: "#fff", m: 0.5, pr: 0.5 }}
                onDelete={() => removeMut.mutate(t.id)}
                onClick={() => openEdit(t)}
                deleteIcon={<Trash2 size={14} />}
              />
            ))}
          </Stack>
        </Paper>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>{editing ? "Editar etiqueta" : "Nueva etiqueta"}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Nombre"
              fullWidth
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
            <Stack direction="row" spacing={2} alignItems="center">
              <TextField
                label="Color"
                type="color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                sx={{ width: 80 }}
                InputLabelProps={{ shrink: true }}
              />
              <Chip label={name || "Vista previa"} sx={{ bgcolor: color, color: "#fff" }} />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancelar</Button>
          <Button variant="contained" onClick={save} disabled={!name.trim()}>
            Guardar
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
