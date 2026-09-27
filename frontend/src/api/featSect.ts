// API helpers para la feature "secciones de proyecto" y el rollover al
// cerrar sprint (move_incomplete_to).
//
// Secciones: GET /api/project-sections/?project=N → [{id,project,name,order}]
//   POST create {project,name} · PATCH/DELETE {id}/ ·
//   POST /api/project-sections/reorder/ {project, section_ids:[…]}
// Task expone `section` (id|null, writable) + `section_name` (solo lectura).
//
// Cierre de sprint con rollover: POST /api/sprints/{id}/close/ acepta
//   {move_incomplete_to: <sprint_id:int>|"backlog"|null}
//   y responde con `moved_incomplete` (nº de tareas movidas).
//   NOTA: el sprintsApi.close legacy de resources.ts enviaba
//   `next_sprint_id`; este helper usa el campo nuevo del contrato.
import { api } from "./client";

type ListResponse<T> = T[] | { results: T[] };

function unwrap<T>(d: ListResponse<T>): T[] {
  return Array.isArray(d) ? d : d.results;
}

// --- Secciones de proyecto (/api/project-sections/) ---

export interface ProjectSection {
  id: number;
  project: number;
  name: string;
  order: number;
}

export const sectionsApi = {
  list: (project: number) =>
    api
      .get<ListResponse<ProjectSection>>("/project-sections/", {
        params: { project },
      })
      .then((r) => unwrap(r.data)),
  create: (data: { project: number; name: string }) =>
    api.post<ProjectSection>("/project-sections/", data).then((r) => r.data),
  update: (id: number, data: { name?: string }) =>
    api.patch<ProjectSection>(`/project-sections/${id}/`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/project-sections/${id}/`),
  /** Reordena: el backend asigna order 0..n-1 siguiendo section_ids. */
  reorder: (project: number, sectionIds: number[]) =>
    api
      .post("/project-sections/reorder/", {
        project,
        section_ids: sectionIds,
      })
      .then((r) => r.data),
};

// --- Cierre de sprint con rollover (/api/sprints/{id}/close/) ---

/** Destino de las tareas incompletas al cerrar un sprint. */
export type MoveIncompleteTo = number | "backlog" | null;

export interface SprintCloseResult {
  message: string;
  /** Nº de tareas incompletas movidas al destino elegido. */
  moved_incomplete?: number;
}

export const sprintCloseApi = {
  close: (id: number, moveIncompleteTo: MoveIncompleteTo) =>
    api
      .post<SprintCloseResult>(`/sprints/${id}/close/`, {
        move_incomplete_to: moveIncompleteTo,
      })
      .then((r) => r.data),
};
