import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Stack,
  Paper,
  Button,
  TextField,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  MenuItem,
  Grid,
} from "@mui/material";
import { Plus, FolderTree } from "lucide-react";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/states";
import { organizationsApi, type OrganizationItem } from "../api/resources";
import { notify } from "../notify";

/**
 * Organizaciones: tenant raíz que agrupa proyectos y controla acceso por roles.
 */
export default function OrganizationsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [dialog, setDialog] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [memberDialog, setMemberDialog] = useState<OrganizationItem | null>(null);
  const [memberEmail, setMemberEmail] = useState("");
  const [memberRole, setMemberRole] = useState("member");

  const { data: orgsData } = useQuery({
    queryKey: ["organizations"],
    queryFn: organizationsApi.list,
  });
  const orgs = Array.isArray(orgsData) ? orgsData : [];

  const createMut = useMutation({
    mutationFn: () => organizationsApi.create({ name, description }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["organizations"] });
      setDialog(false);
      setName("");
      setDescription("");
      notify.success(t("p.admin.orgs.created"));
    },
    onError: () => notify.error(t("p.admin.orgs.errorCreate")),
  });

  const addMemberMut = useMutation({
    mutationFn: () =>
      organizationsApi.addMember(memberDialog!.id, memberEmail, memberRole),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["organizations"] });
      setMemberDialog(null);
      setMemberEmail("");
      notify.success(t("p.admin.orgs.memberAdded"));
    },
    onError: () => notify.error(t("p.admin.orgs.errorAddMember")),
  });

  return (
    <Box>
      <PageHeader
        title={t("p.admin.orgs.title")}
        description={t("p.admin.orgs.description")}
        breadcrumbs={[
          { label: t("p.admin.breadcrumb"), to: "/app/admin" },
          { label: t("p.admin.orgs.title") },
        ]}
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={15} />}
            onClick={() => setDialog(true)}
          >
            {t("p.admin.orgs.new")}
          </Button>
        }
      />

      {orgs.length === 0 ? (
        <EmptyState
          title={t("p.admin.orgs.emptyTitle")}
          description={t("p.admin.orgs.emptyDesc")}
          action={
            <Button variant="contained" onClick={() => setDialog(true)}>
              {t("p.admin.orgs.createFirst")}
            </Button>
          }
        />
      ) : (
        <Grid container spacing={2}>
          {orgs.map((o) => (
            <Grid item xs={12} sm={6} md={4} key={o.id}>
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Stack direction="row" spacing={1.5} alignItems="center" mb={1}>
                  <FolderTree size={20} />
                  <Typography variant="subtitle2" fontWeight={700}>
                    {o.name}
                  </Typography>
                </Stack>
                {o.description && (
                  <Typography variant="body2" color="text.secondary" mb={1}>
                    {o.description}
                  </Typography>
                )}
                <Stack direction="row" spacing={1} alignItems="center">
                  <Chip
                    size="small"
                    label={t("p.admin.orgs.memberCount", { n: o.member_count })}
                    variant="outlined"
                  />
                  <Chip size="small" label={o.slug} variant="outlined" />
                  <Box flex={1} />
                  <Button size="small" onClick={() => setMemberDialog(o)}>
                    {t("p.admin.orgs.addMember")}
                  </Button>
                </Stack>
              </Paper>
            </Grid>
          ))}
        </Grid>
      )}

      <Dialog open={dialog} onClose={() => setDialog(false)} fullWidth maxWidth="xs">
        <DialogTitle>{t("p.admin.orgs.new")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField
              label={t("common.name")}
              fullWidth
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <TextField
              label={t("p.misc.description")}
              multiline
              minRows={2}
              fullWidth
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={!name.trim() || createMut.isPending}
            onClick={() => createMut.mutate()}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={!!memberDialog}
        onClose={() => setMemberDialog(null)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>
          {t("p.admin.orgs.addMemberTo", { name: memberDialog?.name })}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField
              label={t("auth.email")}
              type="email"
              fullWidth
              autoFocus
              value={memberEmail}
              onChange={(e) => setMemberEmail(e.target.value)}
            />
            <TextField
              select
              label={t("p.admin.orgs.roleLabel")}
              fullWidth
              value={memberRole}
              onChange={(e) => setMemberRole(e.target.value)}
            >
              <MenuItem value="member">{t("p.admin.orgs.roles.member")}</MenuItem>
              <MenuItem value="admin">{t("p.admin.orgs.roles.admin")}</MenuItem>
              <MenuItem value="guest">{t("p.admin.orgs.roles.guest")}</MenuItem>
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setMemberDialog(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={!memberEmail.includes("@") || addMemberMut.isPending}
            onClick={() => addMemberMut.mutate()}
          >
            {t("p.admin.orgs.add")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
