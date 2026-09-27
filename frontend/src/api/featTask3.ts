// API helpers para la tercera tanda de features de tareas:
// - Flujo de aprobación de tareas (request_approval / approve / reject).
// - Formularios intake públicos (GET schema + POST submit, sin sesión).
// - "Fuera de la oficina" del usuario actual (PATCH /users/me/).
// Los endpoints públicos usan fetch plano (sin cookies ni CSRF), igual que
// fetchPublicShare en featPublic.ts: el visitante no tiene sesión.
import { api } from "./client";
import { env } from "../env";
import type { Task } from "../types";
import type { AssigneeDetail } from "./featTask";
import type { ProjectMember } from "../types";

// --- Aprobaciones de tarea ---

export type ApprovalStatus = "pending" | "approved" | "rejected";

/** Registro de aprobación expuesto por TaskSerializer (campo `approvals`). */
export interface TaskApproval {
  id: number;
  requester_email?: string;
  approver: number;
  approver_email?: string;
  status: ApprovalStatus;
  note?: string;
  decision_note?: string;
  created_at?: string;
  decided_at?: string | null;
}

/**
 * Campos nuevos del contrato que el backend añade a Task:
 * approvals + pending_approval_for_me + logged_seconds. Se modelan aquí
 * como extensión para no tocar types.ts (compartido con otros agentes).
 */
export interface TaskApprovalFields {
  approvals?: TaskApproval[];
  pending_approval_for_me?: boolean;
  /** Segundos registrados (TimeEntry) acumulados en la tarea. */
  logged_seconds?: number;
}

export type TaskX3 = Task & TaskApprovalFields;

export const approvalsApi = {
  /** Solicita aprobación de la tarea a `approver` (user id). */
  requestApproval: (id: number, data: { approver: number; note?: string }) =>
    api.post<TaskApproval>(`/tasks/${id}/request_approval/`, data).then((r) => r.data),
  /** Aprueba la solicitud pendiente dirigida al usuario actual. */
  approve: (id: number, note?: string) =>
    api
      .post<TaskApproval>(`/tasks/${id}/approve/`, note ? { note } : {})
      .then((r) => r.data),
  /** Rechaza la solicitud pendiente dirigida al usuario actual. */
  reject: (id: number, note?: string) =>
    api
      .post<TaskApproval>(`/tasks/${id}/reject/`, note ? { note } : {})
      .then((r) => r.data),
};

/**
 * Opción de aprobador: miembro del proyecto. El backend puede exponer
 * `user_out_of_office` a nivel de ProjectMember; si está presente lo
 * usamos para el badge OOO en el selector (si no, simplemente no sale).
 */
export interface ApproverOption extends AssigneeDetail {
  out_of_office?: boolean;
}

type MemberOoo = ProjectMember & {
  user_out_of_office?: boolean;
  out_of_office?: boolean;
};

/**
 * Mismo origen que taskXApi.assignableUsers (GET /project-members/?project=N)
 * pero conservando el flag de ausencia cuando el backend lo expone.
 * Comparte queryKey ["project-members", id] en TaskDialog.
 */
export function approverDirectory(projectId: number): Promise<ApproverOption[]> {
  return api
    .get<MemberOoo[] | { results?: MemberOoo[] }>(`/project-members/`, {
      params: { project: projectId },
    })
    .then((r) => {
      const data = r.data;
      const members = Array.isArray(data) ? data : data?.results || [];
      return members
        .filter((m) => typeof m.user === "number")
        .map<ApproverOption>((m) => ({
          id: m.user,
          email: m.user_email || m.email || `#${m.user}`,
          username: m.user_display || m.user_email || `#${m.user}`,
          out_of_office: m.user_out_of_office ?? m.out_of_office ?? undefined,
        }));
    });
}

// --- Formulario intake público (SIN autenticación) ---

export type IntakeFieldType = "text" | "number" | "date" | "select" | "checkbox";

export interface IntakePublicField {
  name: string;
  label: string;
  type: IntakeFieldType;
  required?: boolean;
  options?: string[];
}

/** Contrato de GET /api/intake-forms/public/{token}/ (AllowAny). */
export interface IntakePublicSchema {
  id: number;
  name: string;
  description: string;
  schema: IntakePublicField[];
  enabled: boolean;
}

export class IntakePublicError extends Error {
  status: number;
  constructor(status: number) {
    super(`intake_public_${status}`);
    this.status = status;
  }
}

const publicBase = (token: string) =>
  `${env.VITE_API_URL}/intake-forms/public/${encodeURIComponent(token)}`;

export const intakePublicApi = {
  /** GET público: fetch plano, sin cookies/CSRF ni interceptor de refresh. */
  getSchema: async (token: string): Promise<IntakePublicSchema> => {
    const res = await fetch(`${publicBase(token)}/`);
    if (!res.ok) throw new IntakePublicError(res.status);
    return (await res.json()) as IntakePublicSchema;
  },
  /** POST público {data:{...}} → 201 {id}. */
  submit: async (
    token: string,
    data: Record<string, unknown>,
  ): Promise<{ id: number }> => {
    const res = await fetch(`${publicBase(token)}/submit/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data }),
    });
    if (!res.ok) throw new IntakePublicError(res.status);
    return (await res.json()) as { id: number };
  },
};

// --- Orden manual de tareas (lista reordenable) ---

/**
 * POST /api/tasks/reorder/ {task_ids:[…]} → 200 {updated:n}.
 * El backend asigna position 0..n-1 siguiendo el orden del array; 404 si
 * alguna tarea no es accesible para el usuario, 400 si el payload es malo.
 */
export const taskOrderApi = {
  reorder: (taskIds: number[]) =>
    api
      .post<{ updated: number }>("/tasks/reorder/", { task_ids: taskIds })
      .then((r) => r.data),
};

// --- Fuera de la oficina (/users/me/) ---

/** Campos OOO del contrato de GET/PATCH /api/users/me/. */
export interface UserMeOoo {
  out_of_office?: boolean;
  /** "YYYY-MM-DD" o null. */
  out_of_office_until?: string | null;
}

export const meOooApi = {
  get: () => api.get<UserMeOoo>("/users/me/").then((r) => r.data),
  update: (patch: UserMeOoo) =>
    api.patch<UserMeOoo>("/users/me/", patch).then((r) => r.data),
};
