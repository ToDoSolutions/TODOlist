import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Box,
  Paper,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Typography,
  Chip,
  TextField,
  MenuItem,
  Stack,
  CircularProgress,
} from "@mui/material";
import { Check, X } from "lucide-react";
import PageHeader from "../components/ui/PageHeader";
import { projectsApi, collaborationApi } from "../api/resources";
import { useAuth } from "../auth/AuthContext";

// Matriz que documenta los permisos reales del backend
// (refleja accessible_projects + roles de ProjectMember/OrganizationMembership).
const MATRIX: {
  capability: string;
  owner: boolean;
  admin: boolean;
  member: boolean;
  guest: boolean;
}[] = [
  {
    capability: "p.admin.roles.capability.createProjects",
    owner: true,
    admin: true,
    member: false,
    guest: false,
  },
  {
    capability: "p.admin.roles.capability.editProject",
    owner: true,
    admin: true,
    member: false,
    guest: false,
  },
  {
    capability: "p.admin.roles.capability.deleteProject",
    owner: true,
    admin: false,
    member: false,
    guest: false,
  },
  {
    capability: "p.admin.roles.capability.manageMembers",
    owner: true,
    admin: true,
    member: false,
    guest: false,
  },
  {
    capability: "p.admin.roles.capability.editTasks",
    owner: true,
    admin: true,
    member: true,
    guest: false,
  },
  {
    capability: "p.admin.roles.capability.commentTasks",
    owner: true,
    admin: true,
    member: true,
    guest: false,
  },
  {
    capability: "p.admin.roles.capability.viewAudit",
    owner: true,
    admin: true,
    member: false,
    guest: false,
  },
  {
    capability: "p.admin.roles.capability.editWorkflows",
    owner: true,
    admin: true,
    member: false,
    guest: false,
  },
  {
    capability: "p.admin.roles.capability.manageRisks",
    owner: true,
    admin: true,
    member: false,
    guest: false,
  },
  {
    capability: "p.admin.roles.capability.createIntakeForms",
    owner: true,
    admin: true,
    member: false,
    guest: false,
  },
  {
    capability: "p.admin.roles.capability.viewProjectTasks",
    owner: true,
    admin: true,
    member: true,
    guest: true,
  },
  {
    capability: "p.admin.roles.capability.viewWiki",
    owner: true,
    admin: true,
    member: true,
    guest: true,
  },
  {
    capability: "p.admin.roles.capability.editWiki",
    owner: true,
    admin: true,
    member: false,
    guest: false,
  },
  {
    capability: "p.admin.roles.capability.manageOwnApiKeys",
    owner: true,
    admin: true,
    member: true,
    guest: true,
  },
];

const Cell = ({ ok }: { ok: boolean }) => {
  const { t } = useTranslation();
  return ok ? (
    <Check size={16} color="#43a047" aria-label={t("p.admin.roles.allowed")} />
  ) : (
    <X size={16} color="#bdbdbd" aria-label={t("p.admin.roles.denied")} />
  );
};

// Capacidades derivadas del rol de proyecto (refleja can_edit/can_delete
// de ProjectMember + accessible_projects).
const ROLE_CAPABILITIES: Record<string, string[]> = {
  owner: [
    "p.admin.roles.roleCap.owner.allOfEditor",
    "p.admin.roles.capability.manageMembers",
    "p.admin.roles.roleCap.owner.configureProject",
    "p.admin.roles.roleCap.owner.archiveDelete",
  ],
  editor: [
    "p.admin.roles.roleCap.editor.createEditTasks",
    "p.admin.roles.roleCap.editor.commentAttach",
    "p.admin.roles.roleCap.editor.manageWiki",
    "p.admin.roles.roleCap.editor.viewMetrics",
  ],
  viewer: ["p.admin.roles.roleCap.viewer.viewAll"],
};

export default function RolesPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [selectedProject, setSelectedProject] = useState<number | "">("");

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData) ? projectsData : [];

  // Preselecciona el primer proyecto cuando la lista carga — evita la
  // pantalla vacía de "Selecciona un proyecto" que obliga a un clic
  // extra siempre. Ajuste de estado en render (patrón recomendado):
  // solo corre cuando cambia el primer proyecto, así que el usuario
  // sí puede volver a "" después.
  const firstProjectId = (projects[0] as { id?: number } | undefined)?.id ?? null;
  const [autoSelectedFor, setAutoSelectedFor] = useState<number | null>(firstProjectId);
  if (firstProjectId !== autoSelectedFor) {
    setAutoSelectedFor(firstProjectId);
    if (selectedProject === "" && firstProjectId != null) setSelectedProject(firstProjectId);
  }

  const { data: membersData, isLoading: membersLoading } = useQuery({
    queryKey: ["project-members", selectedProject],
    queryFn: () => collaborationApi.projectMembers.list(Number(selectedProject)),
    enabled: selectedProject !== "",
  });
  const members: { user_email?: string; email?: string; role: string }[] = Array.isArray(
    membersData,
  )
    ? membersData
    : ((membersData as { results?: { role: string }[] } | undefined)?.results ?? []);

  const myMembership = members.find((m) => (m.user_email ?? m.email) === user?.email);
  const project = projects.find((p) => p.id === selectedProject);
  const isOwner = !!project && (project as { owner?: number }).owner === user?.id;
  const effectiveRole = isOwner ? "owner" : myMembership?.role;

  return (
    <Box>
      <PageHeader
        title={t("p.admin.roles.title")}
        description={t("p.admin.roles.description")}
        breadcrumbs={[
          { label: t("p.admin.breadcrumb"), to: "/app/admin" },
          { label: t("p.admin.roles.breadcrumb") },
        ]}
      />

      <Paper variant="outlined" sx={{ overflowX: "auto" }}>
        <Table size="small">
          <caption
            style={{ textAlign: "left", padding: 8, opacity: 0.7, captionSide: "bottom" }}
          >
            {t("p.admin.roles.matrixCaption")}
          </caption>
          <TableHead>
            <TableRow>
              <TableCell>{t("p.admin.roles.colCapability")}</TableCell>
              <TableCell align="center">{t("p.admin.roles.colOwner")}</TableCell>
              <TableCell align="center">{t("p.admin.roles.colAdmin")}</TableCell>
              <TableCell align="center">{t("p.admin.roles.colMember")}</TableCell>
              <TableCell align="center">{t("p.admin.roles.colGuest")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {MATRIX.map((r) => (
              <TableRow key={r.capability}>
                <TableCell>{t(r.capability)}</TableCell>
                <TableCell align="center">
                  <Cell ok={r.owner} />
                </TableCell>
                <TableCell align="center">
                  <Cell ok={r.admin} />
                </TableCell>
                <TableCell align="center">
                  <Cell ok={r.member} />
                </TableCell>
                <TableCell align="center">
                  <Cell ok={r.guest} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

      {/* Permisos efectivos del usuario actual por proyecto */}
      <Paper variant="outlined" sx={{ p: 2, mt: 3 }}>
        <Typography variant="subtitle2" fontWeight={700} mb={1.5}>
          {t("p.admin.roles.effectiveTitle")}
        </Typography>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={2}
          alignItems={{ sm: "center" }}
        >
          <TextField
            select
            size="small"
            label={t("p.admin.roles.projectLabel")}
            sx={{ minWidth: 240 }}
            value={selectedProject}
            onChange={(e) =>
              setSelectedProject(e.target.value === "" ? "" : Number(e.target.value))
            }
          >
            <MenuItem value="">{t("p.admin.roles.selectProject")}</MenuItem>
            {projects.map((p) => (
              <MenuItem key={p.id} value={p.id}>
                {p.name}
              </MenuItem>
            ))}
          </TextField>
          {selectedProject !== "" &&
            (membersLoading ? (
              <CircularProgress size={20} />
            ) : effectiveRole ? (
              <Chip
                color="primary"
                variant="outlined"
                label={t("p.admin.roles.yourRole", { role: effectiveRole })}
              />
            ) : (
              <Chip variant="outlined" label={t("p.admin.roles.noMembership")} />
            ))}
        </Stack>
        {selectedProject !== "" && !membersLoading && (
          <Stack spacing={0.5} mt={1.5}>
            {(ROLE_CAPABILITIES[effectiveRole ?? "viewer"] ?? []).map((c) => (
              <Stack direction="row" spacing={1} alignItems="center" key={c}>
                <Check size={14} color="#43a047" />
                <Typography variant="body2">{t(c)}</Typography>
              </Stack>
            ))}
          </Stack>
        )}
      </Paper>

      <Paper variant="outlined" sx={{ p: 2, mt: 3 }}>
        <Typography variant="subtitle2" fontWeight={700} mb={1}>
          {t("p.admin.roles.inheritanceTitle")}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {t("p.admin.roles.inheritance1")}{" "}
          <Chip
            size="small"
            label={t("p.admin.roles.orgChip")}
            sx={{ mx: 0.5, height: 20 }}
          />{" "}
          {t("p.admin.roles.inheritance2")}{" "}
          <Chip
            size="small"
            label={t("p.admin.roles.projectChip")}
            sx={{ mx: 0.5, height: 20 }}
          />{" "}
          {t("p.admin.roles.inheritance3")}
        </Typography>
      </Paper>
    </Box>
  );
}
