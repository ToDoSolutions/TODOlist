import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Box, CircularProgress, Typography, Alert } from "@mui/material";
import { useAuth } from "../auth/AuthContext";
import { githubApi } from "../api/resources";
import { notify } from "../notify";

export default function GitHubCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { saveTokens } = useAuth();
  const [error, setError] = useState("");

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    if (!code) {
      setError("No se recibió código de autorización");
      return;
    }
    githubApi
      .oauthCallback(code, state || "")
      .then(async (data) => {
        await saveTokens(data.access, data.refresh);
        notify.success(`Sesión iniciada como ${data.github_username}`);
        navigate("/app");
      })
      .catch((e: any) => {
        const msg = e.response?.data?.error || "Error en el callback de GitHub";
        setError(msg);
        notify.error(msg);
      });
  }, [searchParams, navigate, saveTokens]);

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
            Conectando con GitHub...
          </Typography>
        </>
      )}
    </Box>
  );
}
