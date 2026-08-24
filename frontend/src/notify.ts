// notistack v3 ya no exporta enqueueSnackbar/closeSnackbar directamente.
// Usamos el patrón recomendado: guardar la instancia del provider en una
// variable global accesible desde el helper notify.

import type { SnackbarProvider } from "notistack";

let api: SnackbarProvider | null = null;

export function setSnackbarApi(instance: SnackbarProvider | null) {
  api = instance;
}

export const notify = {
  success: (msg: string) => api?.enqueueSnackbar(msg, { variant: "success" }),
  error: (msg: string) => api?.enqueueSnackbar(msg, { variant: "error" }),
  info: (msg: string) => api?.enqueueSnackbar(msg, { variant: "info" }),
  warning: (msg: string) => api?.enqueueSnackbar(msg, { variant: "warning" }),
  dismiss: (key?: string | number) => api?.closeSnackbar(key),
};
