import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Box, Grid, Paper, Typography, Stack, Chip } from "@mui/material";
import {
  Users,
  Shield,
  Key,
  ScrollText,
  Flag,
  Settings,
  Smartphone,
  Lock,
  Webhook,
  GitBranch,
  FolderTree,
  Archive,
  KanbanSquare,
  FileText,
  Timer,
  ListChecks,
} from "lucide-react";
import PageHeader from "../components/ui/PageHeader";
import { useQuery } from "@tanstack/react-query";
import {
  projectsApi,
  collaborationApi,
  featureFlagsApi,
  apiKeysApi,
} from "../api/resources";

const SECTIONS = [
  {
    title: "p.admin.hub.sections.members.title",
    desc: "p.admin.hub.sections.members.desc",
    icon: <Users size={22} />,
    path: "/app/teams",
  },
  {
    title: "p.admin.roles.title",
    desc: "p.admin.hub.sections.roles.desc",
    icon: <Shield size={22} />,
    path: "/app/admin/roles",
  },
  {
    title: "p.admin.orgs.title",
    desc: "p.admin.hub.sections.orgs.desc",
    icon: <FolderTree size={22} />,
    path: "/app/admin/organizations",
  },
  {
    title: "p.admin.hub.sections.workflows.title",
    desc: "p.admin.hub.sections.workflows.desc",
    icon: <KanbanSquare size={22} />,
    path: "/app/workflows",
  },
  {
    title: "p.admin.hub.sections.apiKeys.title",
    desc: "p.admin.hub.sections.apiKeys.desc",
    icon: <Key size={22} />,
    path: "/app/api-keys",
  },
  {
    title: "nav.audit",
    desc: "p.admin.hub.sections.audit.desc",
    icon: <ScrollText size={22} />,
    path: "/app/audit",
  },
  {
    title: "nav.customFields",
    desc: "p.admin.hub.sections.customFields.desc",
    icon: <Settings size={22} />,
    path: "/app/custom-fields",
  },
  {
    title: "p.admin.hub.sections.featureFlags.title",
    desc: "p.admin.hub.sections.featureFlags.desc",
    icon: <Flag size={22} />,
    path: "/app/feature-flags",
  },
  {
    title: "p.admin.hub.sections.webhooks.title",
    desc: "p.admin.hub.sections.webhooks.desc",
    icon: <Webhook size={22} />,
    path: "/app/webhooks",
  },
  {
    title: "nav.offlineSync",
    desc: "p.admin.hub.sections.offlineSync.desc",
    icon: <Smartphone size={22} />,
    path: "/app/offline-sync",
  },
  {
    title: "p.admin.hub.sections.encryption.title",
    desc: "p.admin.hub.sections.encryption.desc",
    icon: <Lock size={22} />,
    path: "/app/encryption",
  },
  {
    title: "section.integrations",
    desc: "p.admin.hub.sections.integrations.desc",
    icon: <GitBranch size={22} />,
    path: "/app/github",
  },
  {
    title: "p.admin.hub.sections.archive.title",
    desc: "p.admin.hub.sections.archive.desc",
    icon: <Archive size={22} />,
    path: "/app/trash",
  },
  {
    title: "p.admin.hub.sections.importExport.title",
    desc: "p.admin.hub.sections.importExport.desc",
    icon: <FileText size={22} />,
    path: "/app/import-export",
  },
  {
    title: "p.admin.hub.sections.sla.title",
    desc: "p.admin.hub.sections.sla.desc",
    icon: <Timer size={22} />,
    path: "/app/admin/sla",
  },
  {
    title: "p.admin.hub.sections.jobs.title",
    desc: "p.admin.hub.sections.jobs.desc",
    icon: <ListChecks size={22} />,
    path: "/app/admin/jobs",
  },
];

/**
 * Hub de administración del workspace: agrupa las pantallas técnicas
 * que antes competían con la navegación diaria.
 */
export default function AdminPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const { data: flags } = useQuery({
    queryKey: ["feature-flags"],
    queryFn: featureFlagsApi.list,
  });
  const { data: keys } = useQuery({ queryKey: ["api-keys"], queryFn: apiKeysApi.list });
  const { data: teams } = useQuery({
    queryKey: ["teams"],
    queryFn: collaborationApi.teams.list,
  });

  const stats = [
    {
      label: "nav.projects",
      value: Array.isArray(projects) ? projects.length : "—",
    },
    {
      label: "nav.teams",
      value: Array.isArray(teams) ? teams.length : "—",
    },
    {
      label: "p.admin.hub.sections.apiKeys.title",
      value: Array.isArray(keys) ? keys.length : "—",
    },
    {
      label: "p.admin.hub.sections.featureFlags.title",
      value: Array.isArray(flags) ? flags.length : "—",
    },
  ];

  return (
    <Box>
      <PageHeader
        title={t("p.admin.hub.title")}
        description={t("p.admin.hub.description")}
      />

      <Stack direction="row" spacing={1.5} mb={3} flexWrap="wrap" useFlexGap>
        {stats.map((s) => (
          <Chip key={s.label} label={`${t(s.label)}: ${s.value}`} variant="outlined" />
        ))}
      </Stack>

      <Grid container spacing={2}>
        {SECTIONS.map((s) => (
          <Grid item xs={12} sm={6} md={4} key={s.path}>
            <Paper
              variant="outlined"
              sx={{
                p: 2,
                cursor: "pointer",
                "&:hover": { borderColor: "primary.main" },
                height: "100%",
              }}
              onClick={() => navigate(s.path)}
              role="link"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && navigate(s.path)}
            >
              <Stack direction="row" spacing={1.5} alignItems="flex-start">
                <Box color="primary.main" mt={0.25}>
                  {s.icon}
                </Box>
                <Box>
                  <Typography variant="subtitle2" fontWeight={700}>
                    {t(s.title)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {t(s.desc)}
                  </Typography>
                </Box>
              </Stack>
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
