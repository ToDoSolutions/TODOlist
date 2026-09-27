import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Paper,
  Typography,
  Stack,
  Button,
  TextField,
  Stepper,
  Step,
  StepLabel,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from "@mui/material";
import { Check, CheckSquare, Folder, Users, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import "../i18n";
import { projectsApi, tasksApi, collaborationApi } from "../api/resources";
import { notify } from "../notify";
import { useUiStore } from "../store/uiStore";

/**
 * Onboarding inicial: guía al usuario hasta su primer proyecto + tarea.
 * Se muestra una vez (flag persistido en uiStore) o vía /app/onboarding.
 */
export default function OnboardingPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const setDone = useUiStore((s) => s.setOnboardingDone);
  const [step, setStep] = useState(0);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [projectName, setProjectName] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [busy, setBusy] = useState(false);

  const STEPS = [
    t("p.auth.onboarding.steps.welcome"),
    t("p.auth.onboarding.steps.project"),
    t("p.auth.onboarding.steps.task"),
    t("p.auth.onboarding.steps.team"),
    t("p.auth.onboarding.steps.done"),
  ];

  const finish = () => {
    setDone();
    navigate("/app");
  };

  const createProject = async () => {
    if (!projectName.trim()) return;
    setBusy(true);
    try {
      const p = await projectsApi.create({ name: projectName.trim() });
      setProjectId(p.id);
      qc.invalidateQueries({ queryKey: ["projects"] });
      setStep(2);
    } catch {
      notify.error(t("p.auth.onboarding.errors.createProject"));
    } finally {
      setBusy(false);
    }
  };

  const createTask = async () => {
    if (!taskTitle.trim() || !projectId) {
      setStep(3);
      return;
    }
    setBusy(true);
    try {
      await tasksApi.create({ title: taskTitle.trim(), project: projectId });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setStep(3);
    } catch {
      notify.error(t("p.auth.onboarding.errors.createTask"));
    } finally {
      setBusy(false);
    }
  };

  const sendInvite = async () => {
    if (!inviteEmail.trim() || !projectId) {
      setStep(4);
      return;
    }
    setBusy(true);
    try {
      await collaborationApi.projectMembers.invite(projectId, {
        email: inviteEmail.trim(),
        role: "member",
      });
      notify.success(t("p.auth.onboarding.inviteSent"));
      setStep(4);
    } catch {
      notify.error(t("p.auth.onboarding.errors.invite"));
      setStep(4);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box maxWidth={560} mx="auto" mt={4}>
      <Stepper activeStep={step} alternativeLabel sx={{ mb: 4 }}>
        {STEPS.map((s) => (
          <Step key={s}>
            <StepLabel>{s}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <Paper variant="outlined" sx={{ p: 4 }}>
        {step === 0 && (
          <Stack spacing={2} alignItems="flex-start">
            <Sparkles size={32} color="#1976d2" />
            <Typography variant="h5" fontWeight={700}>
              {t("p.auth.onboarding.welcomeTitle")}
            </Typography>
            <Typography color="text.secondary">
              {t("p.auth.onboarding.welcomeBody")}
            </Typography>
            <List dense>
              <ListItem>
                <ListItemIcon>
                  <Folder size={16} />
                </ListItemIcon>
                <ListItemText primary={t("p.auth.onboarding.point.project")} />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <CheckSquare size={16} />
                </ListItemIcon>
                <ListItemText primary={t("p.auth.onboarding.point.task")} />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <Users size={16} />
                </ListItemIcon>
                <ListItemText primary={t("p.auth.onboarding.point.team")} />
              </ListItem>
            </List>
            <Button variant="contained" onClick={() => setStep(1)}>
              {t("p.auth.onboarding.start")}
            </Button>
          </Stack>
        )}

        {step === 1 && (
          <Stack spacing={2}>
            <Typography variant="h6" fontWeight={700}>
              {t("p.auth.onboarding.projectTitle")}
            </Typography>
            <TextField
              label={t("p.auth.onboarding.projectName")}
              autoFocus
              required
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createProject()}
            />
            <Stack direction="row" spacing={1}>
              <Button
                variant="contained"
                disabled={!projectName.trim() || busy}
                onClick={createProject}
              >
                {t("p.auth.onboarding.createProject")}
              </Button>
              <Button onClick={() => setStep(2)}>{t("p.auth.onboarding.skip")}</Button>
            </Stack>
          </Stack>
        )}

        {step === 2 && (
          <Stack spacing={2}>
            <Typography variant="h6" fontWeight={700}>
              {t("p.auth.onboarding.taskTitle")}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {projectId
                ? t("p.auth.onboarding.taskHintProject")
                : t("p.auth.onboarding.taskHintInbox")}
            </Typography>
            <TextField
              label={t("p.auth.onboarding.taskName")}
              autoFocus
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createTask()}
            />
            <Stack direction="row" spacing={1}>
              <Button variant="contained" disabled={busy} onClick={createTask}>
                {taskTitle.trim()
                  ? t("p.auth.onboarding.createTask")
                  : t("p.auth.onboarding.continue")}
              </Button>
              <Button onClick={() => setStep(3)}>{t("p.auth.onboarding.skip")}</Button>
            </Stack>
          </Stack>
        )}

        {step === 3 && (
          <Stack spacing={2}>
            <Typography variant="h6" fontWeight={700}>
              {t("p.auth.onboarding.teamTitle")}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t("p.auth.onboarding.teamBody")}
            </Typography>
            <TextField
              label={t("p.auth.email")}
              type="email"
              autoFocus
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              disabled={!projectId}
              helperText={!projectId ? t("p.auth.onboarding.needProject") : undefined}
            />
            <Stack direction="row" spacing={1}>
              <Button
                variant="contained"
                disabled={busy || !projectId || !inviteEmail.trim()}
                onClick={sendInvite}
              >
                {t("p.auth.onboarding.sendInvite")}
              </Button>
              <Button onClick={() => setStep(4)}>{t("p.auth.onboarding.skip")}</Button>
            </Stack>
          </Stack>
        )}

        {step === 4 && (
          <Stack spacing={2} alignItems="flex-start">
            <Check size={32} color="#2e7d32" />
            <Typography variant="h5" fontWeight={700}>
              {t("p.auth.onboarding.doneTitle")}
            </Typography>
            <Typography color="text.secondary">
              {t("p.auth.onboarding.doneBody")}
            </Typography>
            <Button variant="contained" onClick={finish}>
              {t("p.auth.goHome")}
            </Button>
          </Stack>
        )}
      </Paper>

      <Box textAlign="center" mt={2}>
        <Button size="small" onClick={finish}>
          {t("p.auth.onboarding.skipIntro")}
        </Button>
      </Box>
    </Box>
  );
}
