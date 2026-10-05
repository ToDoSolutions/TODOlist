import type { TFunction } from "i18next";

/**
 * apiErrorText — convierte el error de una llamada a la API en un texto
 * listo para mostrar al usuario.
 *
 * - Sin respuesta (offline/timeout) → mensaje de red traducido.
 * - Mensajes DRF conocidos → clave i18n.
 * - Desconocidos → el texto del backend tal cual (mejor información en
 *   inglés que ocultar el detalle), nunca una clave sin resolver.
 */

type ApiErr = {
  response?: {
    status?: number;
    data?: {
      detail?: string;
      error?: string | { code?: string; message?: string };
      non_field_errors?: string[];
      [field: string]: unknown;
    };
  };
};

/** Mensajes frecuentes de DRF → clave i18n bajo common.err.* */
const KNOWN: Record<string, string> = {
  "Unable to log in with provided credentials.": "badCredentials",
  "No active account found with the given credentials": "badCredentials",
  "Invalid token.": "invalidToken",
  "Token is invalid or expired": "invalidToken",
  "This field is required.": "fieldRequired",
  "This field may not be blank.": "fieldRequired",
  "Enter a valid email address.": "invalidEmail",
  "This password is too short. It must contain at least 8 characters.":
    "passwordShort",
  "This password is too common.": "passwordCommon",
  "The two password fields didn't match.": "passwordMismatch",
};

function extractMessage(e: ApiErr): string | null {
  const data = e.response?.data;
  if (!data) return null;
  if (typeof data.detail === "string") return data.detail;
  if (typeof data.error === "string") return data.error;
  if (data.error && typeof data.error === "object" && data.error.message)
    return data.error.message;
  if (Array.isArray(data.non_field_errors) && data.non_field_errors[0])
    return data.non_field_errors[0];
  for (const v of Object.values(data)) {
    if (Array.isArray(v) && typeof v[0] === "string") return v[0];
  }
  return null;
}

export function apiErrorText(e: unknown, t: TFunction, fallbackKey: string): string {
  const err = e as ApiErr;
  const status = err?.response?.status;
  const msg = extractMessage(err);
  const key = msg ? KNOWN[msg] : undefined;

  if (status === 401 && !key) return t("common.err.badCredentials");
  if (status === 403 && !key) return t("common.err.forbidden");
  if (status === 404 && !key) return t("common.err.notFound");
  if (status === 429) return t("common.err.tooMany");
  if (status && status >= 500) return t("common.err.unavailable");
  if (!err?.response && !status) return t("common.err.network");
  if (key) return t(`common.err.${key}`);
  return msg ?? t(fallbackKey);
}
