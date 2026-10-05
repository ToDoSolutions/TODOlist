import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { TableSkeleton } from "../components/ui/skeletons";
import {
  Box,
  Typography,
  Button,
  Paper,
  Stack,
  Chip,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  useTheme,
} from "@mui/material";
import { Plus, Trash2, Tag as TagIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { tagsApi } from "../api/resources";
import { Tag } from "../types";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import PageHeader from "../components/ui/PageHeader";
import { ErrorState } from "../components/ui/states";

export default function TagsPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Tag | null>(null);
  const [name, setName] = useState("");
  const [color, setColor] = useState("#1976d2");

  const {
    data: tagsData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["tags"],
    queryFn: tagsApi.list,
  });
  const tags = Array.isArray(tagsData) ? tagsData : [];

  const createMut = useMutation({
    mutationFn: () => tagsApi.create({ name: name.trim(), color }),
    onSuccess: () => {
      notify.success(t("p.ops.tags.created"));
      qc.invalidateQueries({ queryKey: ["tags"] });
      setOpen(false);
    },
    onError: () => notify.error(t("p.ops.tags.createError")),
  });

  const updateMut = useMutation({
    mutationFn: () => tagsApi.update(editing!.id, { name: name.trim(), color }),
    onSuccess: () => {
      notify.success(t("p.ops.tags.updated"));
      qc.invalidateQueries({ queryKey: ["tags"] });
      setOpen(false);
    },
    onError: () => notify.error(t("p.ops.tags.updateError")),
  });

  const removeMut = useMutation({
    mutationFn: (id: number) => tagsApi.remove(id),
    onSuccess: () => {
      notify.success(t("p.ops.tags.deleted"));
      qc.invalidateQueries({ queryKey: ["tags"] });
    },
    onError: () => notify.error(t("p.ops.tags.deleteError")),
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
      <PageHeader
        title={t("p.ops.tags.title")}
        actions={
          <Button variant="contained" startIcon={<Plus size={18} />} onClick={openNew}>
            {t("p.ops.tags.new")}
          </Button>
        }
      />

      {isError && (
        <ErrorState
          title={t("p.ops.tags.loadError")}
          onRetry={() => void refetch()}
        />
      )}
      {isLoading ? (
        <TableSkeleton />
      ) : tags.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <TagIcon size={32} style={{ color: theme.palette.divider }} />
          <Typography color="text.secondary" mt={1}>
            {t("p.ops.tags.empty")}
          </Typography>
        </Paper>
      ) : (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {tags.map((tag) => (
              <Chip
                key={tag.id}
                label={tag.name}
                sx={{ bgcolor: tag.color, color: "common.white", m: 0.5, pr: 0.5 }}
                onDelete={async () => {
                  if (
                        await confirm(t("p.ops.tags.confirmDelete", { name: tag.name }), {
                          confirmLabel: t("common.delete"),
                        })
                      )
                    removeMut.mutate(tag.id);
                }}
                onClick={() => openEdit(tag)}
                deleteIcon={<Trash2 size={14} />}
              />
            ))}
          </Stack>
        </Paper>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>{editing ? t("p.ops.tags.edit") : t("p.ops.tags.new")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("common.name")}
              fullWidth
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
            <Stack direction="row" spacing={2} alignItems="center">
              <TextField
                label={t("common.color")}
                type="color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                sx={{ width: 80 }}
                InputLabelProps={{ shrink: true }}
              />
              <Chip
                label={name || t("p.ops.tags.preview")}
                sx={{ bgcolor: color, color: "common.white" }}
              />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={save}
            disabled={!name.trim() || createMut.isPending || updateMut.isPending}
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}