import { formatDateTime } from "../lib/dates";
import { useState } from "react";
import { TableSkeleton } from "../components/ui/skeletons";
import {
  Box,
  Typography,
  Button,
  Paper,
  Stack,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  IconButton,
  Tooltip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  useTheme,
} from "@mui/material";
import { Key, Plus, Trash2, Copy, Check, Ban } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiKeysApi } from "../api/resources";
import type { ApiKeyItem } from "../types";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import PageHeader from "../components/ui/PageHeader";
import { useTranslation } from "react-i18next";

export default function ApiKeysPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [form, setForm] = useState({ name: "", scopes: ["read"] });

  const { data: keys, isLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: apiKeysApi.list,
  });

  const createMut = useMutation({
    mutationFn: apiKeysApi.create,
    onSuccess: (data) => {
      setNewKey(data.key);
      notify.success(t("p.admin.apiKeys.created"));
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const revokeMut = useMutation({
    mutationFn: apiKeysApi.revoke,
    onSuccess: () => {
      notify.info(t("p.admin.apiKeys.revoked"));
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const deleteMut = useMutation({
    mutationFn: apiKeysApi.delete,
    onSuccess: () => {
      notify.info(t("p.admin.apiKeys.deleted"));
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const handleCreate = () => {
    createMut.mutate({ name: form.name, scopes: form.scopes });
    setDialogOpen(false);
  };

  const copyKey = () => {
    if (newKey) {
      navigator.clipboard.writeText(newKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const keyList = keys || [];

  return (
    <Box maxWidth={800} mx="auto">
      <PageHeader
        title={
          <>
            <Key size={22} style={{ color: theme.palette.primary.main, verticalAlign: "text-bottom", marginRight: 8 }} />
            {t("nav.apiKeys")}
          </>
        }
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={18} />}
            onClick={() => {
              setForm({ name: "", scopes: ["read"] });
              setNewKey(null);
              setDialogOpen(true);
            }}
          >
            {t("p.admin.apiKeys.new")}
          </Button>
        }
      />

      <Alert severity="info" sx={{ mb: 2 }}>
        {t("p.admin.apiKeys.infoPre")} <code>Authorization: ApiKey &lt;tu_key&gt;</code>{" "}
        {t("p.admin.apiKeys.infoPost")}{" "}
        <a href="/api/docs/" target="_blank" rel="noopener">
          Swagger UI
        </a>{" "}
        ·
        <a href="/api/redoc/" target="_blank" rel="noopener">
          ReDoc
        </a>
      </Alert>

      {isLoading ? (
        <TableSkeleton />
      ) : keyList.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Key size={48} color="text.disabled" />
          <Typography color="text.secondary" mt={1}>
            {t("p.admin.apiKeys.empty")}
          </Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t("common.name")}</TableCell>
                <TableCell>{t("p.admin.apiKeys.colPrefix")}</TableCell>
                <TableCell>{t("p.admin.apiKeys.colScopes")}</TableCell>
                <TableCell>{t("p.admin.apiKeys.colStatus")}</TableCell>
                <TableCell>{t("p.admin.apiKeys.colLastUsed")}</TableCell>
                <TableCell>{t("p.admin.apiKeys.colActions")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {keyList.map((k: ApiKeyItem) => (
                <TableRow key={k.id}>
                  <TableCell>
                    <Typography variant="body2" fontWeight={600}>
                      {k.name}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace">
                      {k.key_prefix}...
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      {(k.scopes || []).map((s: string) => (
                        <Chip
                          key={s}
                          size="small"
                          label={s}
                          sx={{ height: 18, fontSize: 10 }}
                          variant="outlined"
                        />
                      ))}
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={
                        k.is_active
                          ? t("p.admin.apiKeys.statusActive")
                          : t("p.admin.apiKeys.statusRevoked")
                      }
                      sx={{
                        height: 18,
                        fontSize: 10,
                        bgcolor: k.is_active ? "success.main" : "grey.400",
                        color: "common.white",
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">
                      {k.last_used_at
                        ? formatDateTime(k.last_used_at)
                        : t("p.admin.apiKeys.never")}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      {k.is_active && (
                        <Tooltip title={t("p.admin.apiKeys.revoke")}>
                          <IconButton size="small" onClick={() => revokeMut.mutate(k.id)}>
                            <Ban size={14} />
                          </IconButton>
                        </Tooltip>
                      )}
                      <Tooltip title={t("common.delete")}>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={async () => {
                            if (
                              await confirm(
                                t("p.admin.apiKeys.confirmDelete", {
                                  name: k.name,
                                }),
                                {
                                  confirmLabel: t("p.admin.apiKeys.confirmDeleteLabel"),
                                },
                              )
                            )
                              deleteMut.mutate(k.id);
                          }}
                        >
                          <Trash2 size={14} />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Dialog de creación */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.admin.apiKeys.createTitle")}</DialogTitle>
        <DialogContent>
          {newKey ? (
            <Box>
              <Alert severity="warning" sx={{ mb: 2 }}>
                {t("p.admin.apiKeys.keyWarning")}
              </Alert>
              <Paper
                variant="outlined"
                sx={{
                  p: 2,
                  fontFamily: "monospace",
                  wordBreak: "break-all",
                  bgcolor: "action.hover",
                }}
              >
                {newKey}
              </Paper>
              <Button
                startIcon={copied ? <Check size={16} /> : <Copy size={16} />}
                onClick={copyKey}
                sx={{ mt: 1 }}
                color={copied ? "success" : "primary"}
              >
                {copied ? t("p.admin.apiKeys.copied") : t("p.admin.apiKeys.copy")}
              </Button>
            </Box>
          ) : (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <TextField
                label={t("common.name")}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                fullWidth
                size="small"
                helperText={t("p.admin.apiKeys.nameHelper")}
              />
              <FormControl fullWidth size="small">
                <InputLabel>{t("p.admin.apiKeys.colScopes")}</InputLabel>
                <Select
                  multiple
                  value={form.scopes}
                  label={t("p.admin.apiKeys.colScopes")}
                  onChange={(e) =>
                    setForm({ ...form, scopes: e.target.value as string[] })
                  }
                >
                  <MenuItem value="read">{t("p.admin.apiKeys.scopeRead")}</MenuItem>
                  <MenuItem value="write">{t("p.admin.apiKeys.scopeWrite")}</MenuItem>
                  <MenuItem value="admin">{t("p.admin.apiKeys.scopeAdmin")}</MenuItem>
                </Select>
              </FormControl>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setDialogOpen(false);
              setNewKey(null);
            }}
          >
            {newKey ? t("common.close") : t("common.cancel")}
          </Button>
          {!newKey && (
            <Button
              variant="contained"
              onClick={handleCreate}
              disabled={!form.name || createMut.isPending}
            >
              {t("common.create")}
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
}