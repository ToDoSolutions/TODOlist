import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import {
  QueryCache,
  MutationCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { persistQueryClient } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { SnackbarProvider } from "notistack";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDateFns } from "@mui/x-date-pickers/AdapterDateFnsV3";
import { es } from "date-fns/locale";
import App from "./App";
import ErrorBoundary from "./ErrorBoundary";
import { notify, setSnackbarApi } from "./notify";
import { AppThemeProvider } from "./theme-context";
import { ConfirmProvider } from "./components/ConfirmDialog";
import "./i18n";
import { initMonitoring } from "./monitoring";

initMonitoring();

// El service worker se registra desde PwaUpdatePrompt (useRegisterSW),
// que muestra un prompt al haber nueva versión (registerType: "prompt").

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: () =>
      notify.error("No se pudieron cargar los datos. Comprueba tu conexión."),
  }),
  // Red de seguridad para mutaciones sin onError propio: sin esto un POST/PATCH/DELETE
  // que falla en una página sin handler queda silencioso. Si el backend
  // explica el motivo (detail/error del serializer — p.ej. una
  // transición de workflow rechazada) lo mostramos tal cual.
  mutationCache: new MutationCache({
    onError: (err, _vars, _ctx, mutation) => {
      if (mutation.options.onError) return;
      const data = (err as { response?: { data?: unknown } })?.response?.data;
      const detail =
        data && typeof data === "object"
          ? (data as Record<string, unknown>).detail ??
            (data as Record<string, unknown>).error
          : null;
      notify.error(
        typeof detail === "string"
          ? detail
          : "No se pudo completar la operación.",
      );
    },
  }),
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 },
  },
});

// Persistir consultas de referencia en localStorage: la app arranca
// con datos aunque no haya red (complementa la sync offline).
persistQueryClient({
  queryClient,
  persister: createSyncStoragePersister({ storage: window.localStorage }),
  maxAge: 24 * 60 * 60 * 1000,
  dehydrateOptions: {
    shouldDehydrateQuery: (q) =>
      q.state.status === "success" &&
      typeof q.queryKey[0] === "string" &&
      ["projects", "tags", "sprints", "epics"].includes(q.queryKey[0]),
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ReactQueryDevtools initialIsOpen={false} />
      <AppThemeProvider>
        <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={es}>
          <ErrorBoundary>
            <SnackbarProvider
              maxSnack={3}
              anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
              ref={setSnackbarApi}
            >
              <BrowserRouter>
                <ConfirmProvider>
                  <App />
                </ConfirmProvider>
              </BrowserRouter>
            </SnackbarProvider>
          </ErrorBoundary>
        </LocalizationProvider>
      </AppThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
