import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Box, CircularProgress, Typography, Alert } from "@mui/material";
import { useAuth } from "../auth/AuthContext";
import { githubApi, type ApiError } from "../api/resources";
import { notify } from "../notify";
import { useTranslation } from "react-i18next";
import "../i18n";

export default function GitHubCallbackPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { saveTokens } = useAuth();
  const [error, setError] = useState(() =>
    searchParams.get("code") ? "" : t("p.auth.githubCallback.noCode"),
  );

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    if (!code) {
      return;
    }
    githubApi
      .oauthCallback(code, state || "")
      .then(async (data) => {
        await saveTokens(data.access, data.refresh);
        notify.success(
          t("p.auth.githubCallback.signedInAs", {
            username: data.github_username,
          }),
        );
        navigate("/app");
      })
      .catch((e: ApiError) => {
        const msg = e.response?.data?.error || t("p.auth.errors.githubConnect");
        setError(msg);
        notify.error(msg);
      });
  }, [searchParams, navigate, saveTokens, t]);

  return (
    <Box
      display="flex"
      minHeight="100vh"
      alignItems="center"
      justifyContent="center"
      flexDirection="column"
      gap={2}
    >
      {error ? (
        <Alert severity="error">{error}</Alert>
      ) : (
        <>
          <CircularProgress />
          <Typography variant="body1" color="text.secondary">
            {t("p.auth.githubCallback.connecting")}
          </Typography>
        </>
      )}
    </Box>
  );
}
