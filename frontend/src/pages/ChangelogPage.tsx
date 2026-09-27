import { Box, Typography, Paper, Stack, Chip, Divider } from "@mui/material";
import { Sparkles, Bug, Wrench } from "lucide-react";
import { useTranslation } from "react-i18next";
import PageHeader from "../components/ui/PageHeader";
import pkg from "../../package.json";

type ChangeType = "feature" | "fix" | "improvement";

interface Release {
  version: string;
  date: string;
  changes: { type: ChangeType; key: string }[];
}

const TYPE_META: Record<
  ChangeType,
  { labelKey: string; color: "success" | "error" | "info"; icon: React.ReactNode }
> = {
  feature: {
    labelKey: "p.misc.changelog.typeFeature",
    color: "success",
    icon: <Sparkles size={12} />,
  },
  fix: {
    labelKey: "p.misc.changelog.typeFix",
    color: "error",
    icon: <Bug size={12} />,
  },
  improvement: {
    labelKey: "p.misc.changelog.typeImprovement",
    color: "info",
    icon: <Wrench size={12} />,
  },
};

const RELEASES: Release[] = [
  {
    version: pkg.version,
    date: "2026",
    changes: [
      { type: "feature", key: "p.misc.changelog.change1" },
      { type: "feature", key: "p.misc.changelog.change2" },
      { type: "feature", key: "p.misc.changelog.change3" },
      { type: "feature", key: "p.misc.changelog.change4" },
      { type: "feature", key: "p.misc.changelog.change5" },
      { type: "feature", key: "p.misc.changelog.change6" },
      { type: "feature", key: "p.misc.changelog.change7" },
      { type: "feature", key: "p.misc.changelog.change8" },
      { type: "improvement", key: "p.misc.changelog.change9" },
      { type: "improvement", key: "p.misc.changelog.change10" },
      { type: "improvement", key: "p.misc.changelog.change11" },
      { type: "improvement", key: "p.misc.changelog.change12" },
      { type: "fix", key: "p.misc.changelog.change13" },
      { type: "fix", key: "p.misc.changelog.change14" },
    ],
  },
];

/** Novedades del producto: registro visible para el usuario. */
export default function ChangelogPage() {
  const { t } = useTranslation();
  return (
    <Box maxWidth={760} mx="auto">
      <PageHeader
        title={t("p.misc.changelog.title")}
        description={t("p.misc.changelog.description")}
      />
      {RELEASES.map((r) => (
        <Paper key={r.version} variant="outlined" sx={{ p: 2.5, mb: 2 }}>
          <Stack direction="row" spacing={1} alignItems="baseline" mb={1.5}>
            <Typography variant="h6" fontWeight={700}>
              v{r.version}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {r.date}
            </Typography>
          </Stack>
          <Stack spacing={1}>
            {r.changes.map((c, i) => {
              const meta = TYPE_META[c.type];
              return (
                <Stack key={i} direction="row" spacing={1} alignItems="flex-start">
                  <Chip
                    size="small"
                    color={meta.color}
                    variant="outlined"
                    icon={meta.icon as React.ReactElement}
                    label={t(meta.labelKey)}
                    sx={{ height: 20, fontSize: 10, mt: 0.25, flexShrink: 0 }}
                  />
                  <Typography variant="body2">{t(c.key)}</Typography>
                </Stack>
              );
            })}
          </Stack>
        </Paper>
      ))}
      <Divider sx={{ my: 2 }} />
      <Typography variant="caption" color="text.secondary">
        {t("p.misc.changelog.footer")}
      </Typography>
    </Box>
  );
}
