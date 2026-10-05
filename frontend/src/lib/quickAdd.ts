// Parser de captura rápida (quick-add) ES/EN.
// Sintaxis: "Informe mañana 10:00 !alta #Proyecto @tag"
//   fechas:  hoy/today, mañana/tomorrow, lunes…/monday…, en N días|semanas,
//            in N days|weeks, dd/mm[/yyyy]
//   hora:    @HH:MM
//   prior.:  p0–p5, !critica|!critical|!urgente|!urgent (P0), !alta|!high (P2),
//            !media|!medium (P3), !baja|!low (P4)
//   destino: #proyecto (admite nombres con espacios), @etiqueta

import {
  addDays,
  addWeeks,
  isBefore,
  nextDay,
  set,
  startOfToday,
  type Day,
} from "date-fns";

export interface QuickAddResult {
  title: string;
  due_date?: string | null;
  priority?: number;
  project_id?: number;
  tags?: string[];
}

interface QuickAddProject {
  id: number;
  name: string;
}

const norm = (s: string) =>
  s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");

const WEEKDAYS: Record<string, Day> = {
  domingo: 0, sunday: 0,
  lunes: 1, monday: 1,
  martes: 2, tuesday: 2,
  miercoles: 3, miércoles: 3, wednesday: 3,
  jueves: 4, thursday: 4,
  viernes: 5, friday: 5,
  sabado: 6, sábado: 6, saturday: 6,
};

const PRIORITY_WORDS: Record<string, number> = {
  critica: 0, critical: 0, urgente: 0, urgent: 0,
  muyalta: 1, veryhigh: 1,
  alta: 2, high: 2,
  media: 3, medium: 3,
  baja: 4, low: 4,
  algundia: 5, someday: 5,
};

const REL_DAYS_RE = /^(?:en|in)$/i;
const UNITS_RE = /^(?:dias?|days?|semanas?|weeks?)$/i;
const DATE_NUM_RE = /^(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?$/;
const TIME_RE = /^(\d{1,2}):(\d{2})$/;
const PRIORITY_NUM_RE = /^p([0-5])$/i;

/** Extrae "#Nombre de proyecto" casi-insensible a tildes, con espacios. */
function extractProject(
  text: string,
  projects: QuickAddProject[],
): { text: string; projectId?: number } {
  // Nombres más largos primero para preferir la coincidencia más específica.
  const sorted = [...projects].sort((a, b) => b.name.length - a.name.length);
  for (const p of sorted) {
    const haystack = norm(text);
    const needle = `#${norm(p.name)}`;
    const idx = haystack.indexOf(needle);
    if (idx === -1) continue;
    const end = idx + needle.length;
    if (end < haystack.length && !/\s/.test(haystack[end]!)) continue;
    return {
      text: (text.slice(0, idx) + " " + text.slice(end)).trim(),
      projectId: p.id,
    };
  }
  return { text };
}

export function parseQuickAdd(
  input: string,
  opts: { projects?: QuickAddProject[] } = {},
): QuickAddResult | null {
  let text = input.trim();
  if (!text) return null;

  const result: QuickAddResult = { title: "" };
  const tags: string[] = [];
  let date: Date | null = null;
  let time: { h: number; m: number } | null = null;

  // #proyecto (antes de tokenizar: puede tener espacios)
  const proj = extractProject(text, opts.projects ?? []);
  text = proj.text;
  if (proj.projectId !== undefined) result.project_id = proj.projectId;

  const words = text.split(/\s+/).filter(Boolean);
  const kept: string[] = [];

  for (let i = 0; i < words.length; i++) {
    const w = words[i]!;
    const nw = norm(w);

    // @HH:MM (hora) vs @etiqueta
    if (w.startsWith("@")) {
      const tm = TIME_RE.exec(w.slice(1));
      if (tm) {
        time = { h: Math.min(23, +tm[1]!), m: Math.min(59, +tm[2]!) };
      } else if (w.length > 1) {
        tags.push(w.slice(1));
      }
      continue;
    }

    // p0–p5
    const pm = PRIORITY_NUM_RE.exec(w);
    if (pm) {
      result.priority = +pm[1]!;
      continue;
    }

    // !alta / !high / …
    if (w.startsWith("!") && w.length > 1) {
      const p = PRIORITY_WORDS[norm(w.slice(1)).replace(/\s+/g, "")];
      if (p !== undefined) result.priority = p;
      else kept.push(w);
      continue;
    }

    // hoy/mañana · today/tomorrow
    if (nw === "hoy" || nw === "today") {
      date = startOfToday();
      continue;
    }
    if (nw === "manana" || nw === "mañana" || nw === "tomorrow") {
      date = addDays(startOfToday(), 1);
      continue;
    }

    // lunes…/monday… → próxima ocurrencia
    const wd = WEEKDAYS[nw];
    if (wd !== undefined) {
      const candidate = nextDay(startOfToday(), wd);
      date = candidate;
      continue;
    }

    // en N días|semanas · in N days|weeks
    if (REL_DAYS_RE.test(w)) {
      const n = Number(words[i + 1]);
      const unit = words[i + 2];
      if (Number.isFinite(n) && n > 0 && unit && UNITS_RE.test(unit)) {
        const base = startOfToday();
        const normUnit = norm(unit);
        date = normUnit.startsWith("semana") || normUnit.startsWith("week")
          ? addWeeks(base, n)
          : addDays(base, n);
        i += 2;
        continue;
      }
    }

    // dd/mm[/yyyy] → este año; si ya pasó, el siguiente
    const dm = DATE_NUM_RE.exec(w);
    if (dm) {
      const day = +dm[1]!;
      const month = +dm[2]! - 1;
      const year = dm[3] ? +dm[3]! % 10000 + (dm[3]!.length === 2 ? 2000 : 0) : undefined;
      let d = set(startOfToday(), {
        date: day,
        month,
        ...(year !== undefined ? { year } : {}),
      });
      if (year === undefined && isBefore(d, startOfToday())) {
        d = set(d, { year: d.getFullYear() + 1 });
      }
      if (d.getMonth() === month && d.getDate() === day) {
        date = d;
        continue;
      }
    }

    kept.push(w);
  }

  const title = kept.join(" ").trim();
  if (!title) return null;
  result.title = title;

  if (date || time) {
    const base = date ?? startOfToday();
    // Sin hora explícita la tarea vence al final del día.
    const withTime = set(base, {
      hours: time?.h ?? 23,
      minutes: time?.m ?? 59,
      seconds: 0,
      milliseconds: 0,
    });
    result.due_date = withTime.toISOString();
  }
  if (tags.length) result.tags = tags;
  return result;
}
