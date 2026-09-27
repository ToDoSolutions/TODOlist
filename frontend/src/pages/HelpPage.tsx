import {
  Box,
  Typography,
  Paper,
  Stack,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  Divider,
} from "@mui/material";
import { ChevronDown, HelpCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PageHeader from "../components/ui/PageHeader";

interface FaqItem {
  qKey: string;
  aKey: string;
}
interface Section {
  id: string;
  titleKey: string;
  items: FaqItem[];
}

const SECTIONS: Section[] = [
  {
    id: "primeros-pasos",
    titleKey: "p.misc.help.gettingStarted",
    items: [
      { qKey: "p.misc.help.start.q1", aKey: "p.misc.help.start.a1" },
      { qKey: "p.misc.help.start.q2", aKey: "p.misc.help.start.a2" },
      { qKey: "p.misc.help.start.q3", aKey: "p.misc.help.start.a3" },
    ],
  },
  {
    id: "tareas",
    titleKey: "p.misc.help.tasks",
    items: [
      { qKey: "p.misc.help.tasks.q1", aKey: "p.misc.help.tasks.a1" },
      { qKey: "p.misc.help.tasks.q2", aKey: "p.misc.help.tasks.a2" },
      { qKey: "p.misc.help.tasks.q3", aKey: "p.misc.help.tasks.a3" },
      { qKey: "p.misc.help.tasks.q4", aKey: "p.misc.help.tasks.a4" },
    ],
  },
  {
    id: "busqueda",
    titleKey: "p.misc.help.search",
    items: [
      { qKey: "p.misc.help.search.q1", aKey: "p.misc.help.search.a1" },
      { qKey: "p.misc.help.search.q2", aKey: "p.misc.help.search.a2" },
    ],
  },
  {
    id: "colaboracion",
    titleKey: "p.misc.help.collab",
    items: [
      { qKey: "p.misc.help.collab.q1", aKey: "p.misc.help.collab.a1" },
      { qKey: "p.misc.help.collab.q2", aKey: "p.misc.help.collab.a2" },
      { qKey: "p.misc.help.collab.q3", aKey: "p.misc.help.collab.a3" },
    ],
  },
  {
    id: "offline",
    titleKey: "p.misc.help.offline",
    items: [
      { qKey: "p.misc.help.offline.q1", aKey: "p.misc.help.offline.a1" },
      { qKey: "p.misc.help.offline.q2", aKey: "p.misc.help.offline.a2" },
    ],
  },
  {
    id: "notificaciones",
    titleKey: "nav.notifications",
    items: [
      { qKey: "p.misc.help.notifs.q1", aKey: "p.misc.help.notifs.a1" },
      { qKey: "p.misc.help.notifs.q2", aKey: "p.misc.help.notifs.a2" },
    ],
  },
];

const QUICK_LINKS: { labelKey: string; to: string }[] = [
  { labelKey: "nav.myWork", to: "/app/my-work" },
  { labelKey: "p.misc.help.linkSearch", to: "/app/search" },
  { labelKey: "nav.offlineSync", to: "/app/offline-sync" },
  { labelKey: "p.misc.help.linkChangelog", to: "/app/changelog" },
];

/** Centro de ayuda: guía rápida + FAQ por áreas. */
export default function HelpPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <Box maxWidth={860} mx="auto">
      <PageHeader
        title={t("p.misc.help.title")}
        description={t("p.misc.help.description")}
      />

      <Stack direction="row" spacing={1} mb={3} flexWrap="wrap" useFlexGap>
        {QUICK_LINKS.map((l) => (
          <Chip
            key={l.to}
            label={t(l.labelKey)}
            onClick={() => navigate(l.to)}
            clickable
            variant="outlined"
          />
        ))}
      </Stack>

      {SECTIONS.map((s) => (
        <Box key={s.id} mb={3}>
          <Typography variant="subtitle1" fontWeight={700} mb={1} id={s.id}>
            {t(s.titleKey)}
          </Typography>
          {s.items.map((item) => (
            <Accordion key={item.qKey} variant="outlined" disableGutters>
              <AccordionSummary expandIcon={<ChevronDown size={16} />}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <HelpCircle size={14} />
                  <Typography variant="body2" fontWeight={600}>
                    {t(item.qKey)}
                  </Typography>
                </Stack>
              </AccordionSummary>
              <AccordionDetails>
                <Typography variant="body2" color="text.secondary">
                  {t(item.aKey)}
                </Typography>
              </AccordionDetails>
            </Accordion>
          ))}
        </Box>
      ))}

      <Divider sx={{ my: 3 }} />
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle2" fontWeight={700} mb={1}>
          {t("p.misc.help.supportTitle")}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {t("p.misc.help.supportBody")}
        </Typography>
      </Paper>
    </Box>
  );
}
