import { Component, ErrorInfo, ReactNode } from "react";
import { Box, Typography, Button, Paper } from "@mui/material";

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

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Box p={3} display="flex" justifyContent="center" minHeight="100vh" alignItems="center">
          <Paper sx={{ p: 4, maxWidth: 700, width: "100%" }}>
            <Typography variant="h5" color="error" gutterBottom>
              Error en la aplicación
            </Typography>
            <Typography variant="body1" sx={{ mt: 2, fontFamily: "monospace", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
              {this.state.error?.toString()}
            </Typography>
            {this.state.errorInfo && (
              <Typography variant="body2" sx={{ mt: 2, fontFamily: "monospace", whiteSpace: "pre-wrap", wordBreak: "break-word", color: "text.secondary" }}>
                {this.state.errorInfo.componentStack}
              </Typography>
            )}
            <Button
              variant="contained"
              sx={{ mt: 3 }}
              onClick={() => {
                this.setState({ hasError: false, error: null, errorInfo: null });
                window.location.href = "/";
              }}
            >
              Recargar
            </Button>
          </Paper>
        </Box>
      );
    }
    return this.props.children;
  }
}
