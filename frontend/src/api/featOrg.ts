/**
 * API de funciones organizativas (feature "org"): portafolios, plantillas
 * de proyecto y etiquetas de estado personalizadas por proyecto.
 *
 * Separada de resources.ts porque pertenece a un batch de features distinto;
 * reutiliza el mismo cliente axios (auth por cookie + CSRF + refresh).
 */
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { TaskState } from "../types";

type ListResponse<T> = T[] | { results: T[] };

function unwrap<T>(d: ListResponse<T>): T[] {
  return Array.isArray(d) ? d : d.results;
}

// --- Portafolios (/api/portfolios/) ---

export interface Portfolio {
  id: number;
  name: string;
  color: string;
  project_ids: number[];
}

export const portfoliosApi = {
  list: () =>
    api.get<ListResponse<Portfolio>>("/portfolios/").then((r) => unwrap(r.data)),
  create: (p: Partial<Portfolio>) =>
    api.post<Portfolio>("/portfolios/", p).then((r) => r.data),
  update: (id: number, p: Partial<Portfolio>) =>
    api.patch<Portfolio>(`/portfolios/${id}/`, p).then((r) => r.data),
  remove: (id: number) => api.delete(`/portfolios/${id}/`),
};

// --- Plantillas de proyecto (/api/project-templates/) ---

export interface ProjectTemplateTask {
  title: string;
  description?: string;
  priority: number;
  task_type?: string;
  estimate_hours?: number;
}

export interface ProjectTemplateConfig {
  tasks: ProjectTemplateTask[];
  tags: string[];
}

export interface ProjectTemplate {
  id: number;
  name: string;
  description: string;
  config: ProjectTemplateConfig;
  is_builtin: boolean;
  /** Publicada en el catálogo comunitario (visible para todos). */
  is_public?: boolean;
  /** Veces que se ha aplicado desde el catálogo. */
  use_count?: number;
  /** username/email del autor (solo lectura). */
  author?: string;
  /** La plantilla pertenece al usuario actual. */
  is_mine?: boolean;
}

export interface ApplyTemplateResult {
  project_id: number;
  tasks_created: number;
}

export const projectTemplatesApi = {
  list: (community?: boolean) =>
    api
      .get<ListResponse<ProjectTemplate>>("/project-templates/", {
        params: community ? { community: "true" } : undefined,
      })
      .then((r) => unwrap(r.data)),
  create: (p: Partial<ProjectTemplate>) =>
    api.post<ProjectTemplate>("/project-templates/", p).then((r) => r.data),
  update: (id: number, p: Partial<ProjectTemplate>) =>
    api.patch<ProjectTemplate>(`/project-templates/${id}/`, p).then((r) => r.data),
  remove: (id: number) => api.delete(`/project-templates/${id}/`),
  /** Crea un proyecto nuevo a partir de la plantilla. */
  apply: (id: number, data: { name: string; description?: string }) =>
    api
      .post<ApplyTemplateResult>(`/project-templates/${id}/apply/`, data)
      .then((r) => r.data),
  /** Guarda la estructura de un proyecto existente como plantilla. */
  fromProject: (data: {
    project_id: number;
    name: string;
    description?: string;
    public?: boolean;
  }) =>
    api
      .post<ProjectTemplate>("/project-templates/from_project/", data)
      .then((r) => r.data),
};

// --- Etiquetas de estado por proyecto (/api/state-labels/) ---

export interface StateLabel {
  id: number;
  project?: number;
  state: TaskState;
  label: string;
}

export const stateLabelsApi = {
  list: (projectId: number) =>
    api
      .get<ListResponse<StateLabel>>("/state-labels/", {
        params: { project: projectId },
      })
      .then((r) => unwrap(r.data)),
  /** POST upserta por (project, state). */
  upsert: (data: { project: number; state: TaskState; label: string }) =>
    api.post<StateLabel>("/state-labels/", data).then((r) => r.data),
  remove: (id: number) => api.delete(`/state-labels/${id}/`),
};

/**
 * Etiquetas personalizadas de estado del proyecto actual.
 *
 * Pensado para el Kanban/lista: `labelFor(state)` devuelve la etiqueta
 * custom o `undefined` si el estado no tiene override (usar entonces la
 * traducción por defecto `t(TASK_STATE_I18N_KEYS[state])`).
 *
 * Uso típico en el board:
 *   const { labelFor } = useStateLabels(projectId);
 *   const title = labelFor(task.state) ?? t(TASK_STATE_I18N_KEYS[task.state]);
 */
export function useStateLabels(projectId: number | null | undefined) {
  const query = useQuery({
    queryKey: ["state-labels", projectId],
    queryFn: () => stateLabelsApi.list(projectId as number),
    enabled: typeof projectId === "number" && Number.isFinite(projectId),
  });

  /** Mapa state → etiqueta custom (solo overrides, sin defaults). */
  const labels = useMemo(() => {
    const map = {} as Partial<Record<TaskState, string>>;
    for (const item of query.data ?? []) {
      map[item.state] = item.label;
    }
    return map;
  }, [query.data]);

  /** Etiqueta custom del estado o undefined si usa la default. */
  const labelFor = useMemo(
    () =>
      (state: TaskState): string | undefined =>
        labels[state],
    [labels],
  );

  return {
    /** Filas crudas [{id, state, label}] — necesarias para reset (DELETE {id}). */
    rows: query.data ?? [],
    labels,
    labelFor,
    isLoading: query.isLoading,
    isError: query.isError,
  };
}
