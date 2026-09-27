import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Typography,
  Stack,
  Paper,
  Button,
  TextField,
  MenuItem,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert,
  InputAdornment,
} from "@mui/material";
import { Plus, Trash2, Copy, Link2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/states";
import { projectsApi } from "../api/resources";
import { shareLinksApi, type ShareLinkItem } from "../api/featPublic";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import { formatDateTime } from "../lib/dates";

const shareUrl = (token: string) => `${window.location.origin}/share/${token}`;

/**
 * Gestión de enlaces compartidos: cada enlace expone una vista pública de
 * solo lectura del proyecto en /share/:token (SharePage, sin sesión).
 */
export default function ShareLinksPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [project, setProject] = useState<number | "">("");
  const [created, setCreated] = useState<ShareLinkItem | null>(null);

  const {
    data: linksData,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["share-links"],
    queryFn: shareLinksApi.list,
  });
  const links = Array.isArray(linksData) ? linksData : [];

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = useMemo(
    () => (Array.isArray(projectsData) ? projectsData : []),
    [projectsData],
  );
  const projectName = useMemo(
    () => new Map(projects.map((p) => [p.id, p.name])),
    [projects],
  );

  const createMut = useMutation({
    mutationFn: (projectId: number) => shareLinksApi.create(projectId),
    onSuccess: (link) => {
      qc.invalidateQueries({ queryKey: ["share-links"] });
      setCreated(link);
    },
    onError: () => notify.error(t("p.public.links.createError")),
  });

  const revokeMut = useMutation({
    mutationFn: (id: number) => shareLinksApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["share-links"] });
      notify.success(t("p.public.links.revokedOk"));
    },
  });

  const copyLink = (token: string) => {
    void navigator.clipboard.writeText(shareUrl(token));
    notify.success(t("p.public.links.copied"));
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setProject("");
    setCreated(null);
  };

  return (
    <Box>
      <PageHeader
        title={t("p.public.links.title")}
        description={t("p.public.links.description")}
        breadcrumbs={[{ label: t("p.public.links.title") }]}
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={15} />}
            onClick={() => setDialogOpen(true)}
          >
            {t("p.public.links.new")}
          </Button>
        }
      />

      {isLoading && <CircularProgress />}
      {isError && <Alert severity="error">{t("p.public.links.loadError")}</Alert>}
      {!isLoading && !isError && links.length === 0 && (
        <EmptyState
          title={t("p.public.links.emptyTitle")}
          description={t("p.public.links.emptyDesc")}
          action={
            <Button variant="contained" onClick={() => setDialogOpen(true)}>
              {t("p.public.links.createFirst")}
            </Button>
          }
        />
      )}
      {!isLoading && !isError && links.length > 0 && (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t("p.public.links.colProject")}</TableCell>
                <TableCell>{t("p.public.links.colCreated")}</TableCell>
                <TableCell>{t("p.public.links.colStatus")}</TableCell>
                <TableCell align="right">{t("p.public.links.colActions")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {links.map((link) => {
                const name = projectName.get(link.project) ?? `#${link.project}`;
                return (
                  <TableRow key={link.id}>
                    <TableCell>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Link2 size={14} />
                        <Typography variant="body2">{name}</Typography>
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {formatDateTime(link.created_at) || "—"}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        variant="outlined"
                        color={link.is_active ? "success" : "default"}
                        label={
                          link.is_active
                            ? t("p.public.links.active")
                            : t("p.public.links.revoked")
                        }
                      />
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        aria-label={t("p.public.links.copyLink")}
                        disabled={!link.is_active}
                        onClick={() => copyLink(link.token)}
                      >
                        <Copy size={15} />
                      </IconButton>
                      <IconButton
                        size="small"
                        color="error"
                        aria-label={t("p.public.links.revoke")}
                        disabled={!link.is_active}
                        onClick={async () => {
                          if (await confirm(t("p.public.links.confirmRevoke", { name })))
                            revokeMut.mutate(link.id);
                        }}
                      >
                        <Trash2 size={15} />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={dialogOpen} onClose={closeDialog} fullWidth maxWidth="sm">
        <DialogTitle>
          {created ? t("p.public.links.createdTitle") : t("p.public.links.new")}
        </DialogTitle>
        <DialogContent dividers>
          {created ? (
            <Stack spacing={1.5}>
              <Typography variant="body2" color="text.secondary">
                {t("p.public.links.createdDesc")}
              </Typography>
              <TextField
                size="small"
                fullWidth
                value={shareUrl(created.token)}
                InputProps={{
                  readOnly: true,
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        size="small"
                        aria-label={t("p.public.links.copyLink")}
                        onClick={() => copyLink(created.token)}
                      >
                        <Copy size={15} />
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
                onFocus={(e) => e.target.select()}
              />
            </Stack>
          ) : (
            <TextField
              select
              fullWidth
              required
              label={t("p.public.links.selectProject")}
              value={project}
              onChange={(e) => setProject(Number(e.target.value))}
              sx={{ mt: 1 }}
            >
              {projects.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name}
                </MenuItem>
              ))}
            </TextField>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDialog}>{t("common.close")}</Button>
          {!created && (
            <Button
              variant="contained"
              disabled={project === "" || createMut.isPending}
              onClick={() => createMut.mutate(Number(project))}
            >
              {t("common.create")}
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
}
