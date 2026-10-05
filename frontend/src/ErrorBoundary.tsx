import { Component, ErrorInfo, ReactNode } from "react";
import { Box, Typography, Button, Paper } from "@mui/material";
import i18n from "./i18n";
import { captureError } from "./monitoring";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  override componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    console.error("ErrorBoundary caught:", error, errorInfo);
    captureError(error, { componentStack: errorInfo.componentStack });
  }

  override render() {
    if (this.state.hasError) {
      return (
        <Box
          p={3}
          display="flex"
          justifyContent="center"
          minHeight="100vh"
          alignItems="center"
        >
          <Paper sx={{ p: 4, maxWidth: 700, width: "100%" }}>
            <Typography variant="h5" color="error" gutterBottom role="alert">
              {i18n.t("common.appError.title")}
            </Typography>
            <Typography variant="body1" sx={{ mt: 1 }}>
              {i18n.t("common.appError.desc")}
            </Typography>
            {this.state.error && (
              <details style={{ marginTop: 16 }}>
                <summary style={{ cursor: "pointer" }}>
                  {i18n.t("common.appError.details")}
                </summary>
                <Typography
                  variant="body2"
                  component="pre"
                  sx={{
                    mt: 1,
                    fontFamily: "monospace",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    color: "text.secondary",
                    fontSize: "0.75rem",
                  }}
                >
                  {this.state.error.toString()}
                  {this.state.errorInfo?.componentStack ?? ""}
                </Typography>
              </details>
            )}
            <Button
              variant="contained"
              sx={{ mt: 3 }}
              onClick={() => {
                this.setState({ hasError: false, error: null, errorInfo: null });
                window.location.href = "/";
              }}
            >
              {i18n.t("common.appError.reload")}
            </Button>
          </Paper>
        </Box>
      );
    }
    return this.props.children;
  }
}
