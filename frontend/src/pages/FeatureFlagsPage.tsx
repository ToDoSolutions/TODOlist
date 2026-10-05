import { useState } from "react";
import { useTranslation } from "react-i18next";
import { TableSkeleton } from "../components/ui/skeletons";
import PageHeader from "../components/ui/PageHeader";
import {
  Box,
  Typography,
  Paper,
  Button,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Chip,
  Switch,
  FormControlLabel,
  useTheme,
} from "@mui/material";
import { Plus, Trash2, Flag, Check, X } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { featureFlagsApi, type ApiPayload } from "../api/resources";
import type { FeatureFlag } from "../types";
import { notify } from "../notify";

interface FlagForm {
  key: string;
  name: string;
  description: string;
  is_enabled: boolean;
  enabled_percentage: number;
}

const EMPTY_FORM: FlagForm = {
  key: "",
  name: "",
  description: "",
  is_enabled: false,
  enabled_percentage: 100,
};

export default function FeatureFlagsPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [form, setForm] = useState<FlagForm>(EMPTY_FORM);

  // Check section
  const [checkKey, setCheckKey] = useState("");
  const [checkResult, setCheckResult] = useState<{
    enabled?: boolean;
    reason?: string;
  } | null>(null);
  const [checkLoading, setCheckLoading] = useState(false);

  const { data: flags, isLoading } = useQuery({
    queryKey: ["feature-flags"],
    queryFn: featureFlagsApi.list,
  });

  const createMut = useMutation({
    mutationFn: featureFlagsApi.create,
    onSuccess: () => {
      notify.success(t("p.admin.flags.created"));
      qc.invalidateQueries({ queryKey: ["feature-flags"] });
      setDialogOpen(false);
    },
    onError: () => notify.error(t("p.admin.flags.errorCreate")),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => featureFlagsApi.remove(id),
    onSuccess: () => {
      notify.info(t("p.admin.flags.deleted"));
      qc.invalidateQueries({ queryKey: ["feature-flags"] });
      setDeleteId(null);
    },
    onError: () => notify.error(t("p.admin.flags.errorDelete")),
  });

  const handleCreate = () => {
    createMut.mutate({
      key: form.key,
      name: form.name,
      description: form.description,
      is_enabled: form.is_enabled,
      enabled_percentage: form.enabled_percentage,
    });
  };

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiPayload }) =>
      featureFlagsApi.update(id, data),
    onSuccess: () => {
      notify.success(t("p.admin.flags.updated"));
      qc.invalidateQueries({ queryKey: ["feature-flags"] });
    },
    onError: () => notify.error(t("p.admin.flags.errorUpdate")),
  });

  const handleToggle = (flag: FeatureFlag) => {
    updateMut.mutate({
      id: flag.id,
      data: {
        key: flag.key,
        name: flag.name,
        description: flag.description || "",
        is_enabled: !flag.is_enabled,
        enabled_percentage: flag.enabled_percentage ?? 100,
      },
    });
  };

  const handleCheck = async () => {
    if (!checkKey.trim()) {
      notify.warning(t("p.admin.flags.enterKey"));
      return;
    }
    setCheckLoading(true);
    setCheckResult(null);
    try {
      const res = await featureFlagsApi.check(checkKey.trim());
      setCheckResult(res);
    } catch {
      notify.error(t("p.admin.flags.errorCheck"));
    } finally {
      setCheckLoading(false);
    }
  };

  const flagList: FeatureFlag[] = Array.isArray(flags)
    ? flags
    : (flags as { results?: FeatureFlag[] } | undefined)?.results || [];

  return (
    <Box maxWidth={900} mx="auto">
      <PageHeader
        title={
          <>
            <Flag size={22} style={{ color: theme.palette.primary.main, verticalAlign: "text-bottom", marginRight: 8 }} />
            {t("nav.featureFlags")}
          </>
        }
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={18} />}
            onClick={() => {
              setForm(EMPTY_FORM);
              setDialogOpen(true);
            }}
          >
            {t("p.admin.flags.new")}
          </Button>
        }
      />

      {isLoading ? (
        <TableSkeleton />
      ) : flagList.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Flag size={48} color="text.disabled" />
          <Typography color="text.secondary" mt={1}>
            {t("p.admin.flags.empty")}
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={2}>
          {flagList.map((f) => (
            <Paper key={f.id ?? f.key} variant="outlined" sx={{ p: 2 }}>
              <Stack
                direction="row"
                alignItems="flex-start"
                justifyContent="space-between"
              >
                <Box sx={{ flex: 1 }}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Typography variant="subtitle1" fontWeight={600}>
                      {f.name || f.key}
                    </Typography>
                    <Chip
                      size="small"
                      label={f.key}
                      sx={{ height: 20, fontSize: 10 }}
                      variant="outlined"
                    />
                  </Stack>
                  {f.description && (
                    <Typography variant="body2" color="text.secondary" mt={0.5}>
                      {f.description}
                    </Typography>
                  )}
                  <Stack
                    direction="row"
                    spacing={1}
                    mt={1}
                    alignItems="center"
                    flexWrap="wrap"
                    useFlexGap
                  >
                    <Chip
                      size="small"
                      label={
                        f.is_enabled
                          ? t("p.admin.flags.enabled")
                          : t("p.admin.flags.disabled")
                      }
                      sx={{
                        height: 22,
                        fontSize: 11,
                        bgcolor: f.is_enabled ? "success.main" : "grey.400",
                        color: "common.white",
                      }}
                      icon={
                        f.is_enabled ? (
                          <Check
                            size={12}
                            style={{ color: theme.palette.common.white }}
                          />
                        ) : (
                          <X size={12} style={{ color: theme.palette.common.white }} />
                        )
                      }
                    />
                    <Chip
                      size="small"
                      label={`${f.enabled_percentage ?? 100}%`}
                      sx={{ height: 22, fontSize: 11 }}
                      variant="outlined"
                    />
                    {(f.enabled_users || []).length > 0 && (
                      <Chip
                        size="small"
                        label={t("p.admin.flags.userCount", {
                          n: (f.enabled_users || []).length,
                        })}
                        sx={{ height: 22, fontSize: 11 }}
                        variant="outlined"
                      />
                    )}
                  </Stack>
                </Box>
                <Stack direction="row" spacing={0.5} alignItems="center">
                  <Tooltip
                    title={
                      f.is_enabled
                        ? t("p.admin.flags.disable")
                        : t("p.admin.flags.enable")
                    }
                  >
                    <IconButton size="small" onClick={() => handleToggle(f)}>
                      {f.is_enabled ? <X size={16} /> : <Check size={16} />}
                    </IconButton>
                  </Tooltip>
                  <Tooltip title={t("common.delete")}>
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => setDeleteId(f.id)}
                    >
                      <Trash2 size={16} />
                    </IconButton>
                  </Tooltip>
                </Stack>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      {/* Sección de verificación */}
      <Paper variant="outlined" sx={{ p: 3, mt: 4 }}>
        <Typography variant="h6" fontWeight={700} mb={2}>
          {t("p.admin.flags.checkTitle")}
        </Typography>
        <Stack direction="row" spacing={1} mb={2}>
          <TextField
            label={t("p.admin.flags.checkKeyLabel")}
            value={checkKey}
            onChange={(e) => setCheckKey(e.target.value)}
            size="small"
          />
          <Button variant="outlined" onClick={handleCheck} disabled={checkLoading}>
            {t("p.admin.flags.check")}
          </Button>
        </Stack>

        {checkLoading && (
          <Box display="flex" justifyContent="center" py={2}>
            <CircularProgress size={24} />
          </Box>
        )}

        {checkResult && !checkLoading && (
          <Alert
            severity={checkResult.enabled ? "success" : "info"}
            icon={checkResult.enabled ? <Check size={18} /> : <X size={18} />}
          >
            {t("p.admin.flags.checkResultPre")} <strong>{checkKey}</strong>{" "}
            {t("p.admin.flags.checkResultIs")}{" "}
            <strong>
              {checkResult.enabled
                ? t("p.admin.flags.stateEnabled")
                : t("p.admin.flags.stateDisabled")}
            </strong>
            {checkResult.reason && ` (${checkResult.reason})`}
          </Alert>
        )}
      </Paper>

      {/* Dialog de creación */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.admin.flags.createTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("p.admin.flags.keyLabel")}
              value={form.key}
              onChange={(e) => setForm({ ...form, key: e.target.value })}
              fullWidth
              size="small"
              helperText={t("p.admin.flags.keyHelper")}
            />
            <TextField
              label={t("common.name")}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
              size="small"
            />
            <TextField
              label={t("p.misc.description")}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              fullWidth
              size="small"
              multiline
              rows={2}
            />
            <TextField
              label={t("p.admin.flags.percentLabel")}
              value={form.enabled_percentage}
              onChange={(e) =>
                setForm({ ...form, enabled_percentage: Number(e.target.value) })
              }
              fullWidth
              size="small"
              type="number"
              inputProps={{ min: 0, max: 100 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_enabled}
                  onChange={(e) => setForm({ ...form, is_enabled: e.target.checked })}
                />
              }
              label={t("p.admin.flags.enabled")}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={!form.key || createMut.isPending}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog de confirmación de borrado */}
      <Dialog
        open={deleteId !== null}
        onClose={() => setDeleteId(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>{t("p.admin.flags.deleteTitle")}</DialogTitle>
        <DialogContent>
          <Alert severity="warning">{t("p.admin.flags.deleteConfirm")}</Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteId(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            color="error"
            onClick={() => deleteId && deleteMut.mutate(deleteId)}
            disabled={deleteMut.isPending}
          >
            {t("common.delete")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}