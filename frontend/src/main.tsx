import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SnackbarProvider } from "notistack";
import App from "./App";
import ErrorBoundary from "./ErrorBoundary";
import { setSnackbarApi } from "./notify";
import { AppThemeProvider } from "./theme-context";
import { registerSW } from "virtual:pwa-register";

// Registrar service worker para PWA
registerSW({ immediate: true });

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppThemeProvider>
        <ErrorBoundary>
          <SnackbarProvider
            maxSnack={3}
            anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
            ref={setSnackbarApi}
          >
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </SnackbarProvider>
        </ErrorBoundary>
      </AppThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
