// Helpers de formato de fecha/hora con locale es/en según i18n.
// Todas aceptan string ISO, Date, null/undefined y devuelven "" en
// entrada vacía o inválida para simplificar los templates.
import { format, formatDistanceToNow, isValid, parseISO } from "date-fns";
import { es, enUS } from "date-fns/locale";
import i18n from "../i18n";

type DateInput = string | Date | null | undefined;

/** Locale date-fns activo (para formatos puntuales fuera de los helpers). */
export function dateLocale() {
  return i18n.language?.startsWith("es") ? es : enUS;
}

const locale = dateLocale;

function toDate(value: DateInput): Date | null {
  if (!value) return null;
  const d = typeof value === "string" ? parseISO(value) : value;
  return isValid(d) ? d : null;
}

/** "29 sept 2026" — solo fecha. */
export function formatDate(value: DateInput): string {
  const d = toDate(value);
  return d ? format(d, "d MMM yyyy", { locale: locale() }) : "";
}

/** "29 sept 2026, 14:30" — fecha y hora. */
export function formatDateTime(value: DateInput): string {
  const d = toDate(value);
  return d ? format(d, "d MMM yyyy, HH:mm", { locale: locale() }) : "";
}

/** "14:30" — solo hora. */
export function formatTime(value: DateInput): string {
  const d = toDate(value);
  return d ? format(d, "HH:mm") : "";
}

/** "hace 3 días" / "3 days ago" — distancia relativa a ahora. */
export function formatRelative(value: DateInput): string {
  const d = toDate(value);
  return d
    ? formatDistanceToNow(d, { addSuffix: true, locale: locale() })
    : "";
}

/** "4 oct" — fecha corta sin año para chips compactos. */
export function formatShort(value: DateInput): string {
  const d = toDate(value);
  return d ? format(d, "d MMM", { locale: locale() }) : "";
}

/** "4 oct 12:01" — fecha y hora compacta sin año (feeds, comentarios). */
export function formatDateTimeShort(value: DateInput): string {
  const d = toDate(value);
  return d ? format(d, "d MMM HH:mm", { locale: locale() }) : "";
}

/** "sábado 4 octubre" — nombre de día para encabezados de grupo. */
export function formatDayName(value: DateInput): string {
  const d = toDate(value);
  return d ? format(d, "EEEE d MMMM", { locale: locale() }) : "";
}

/** "octubre 2026" — mes y año. */
export function formatMonthYear(value: DateInput): string {
  const d = toDate(value);
  return d ? format(d, "MMMM yyyy", { locale: locale() }) : "";
}
