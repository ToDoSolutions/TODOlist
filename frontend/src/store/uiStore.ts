import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Density = "comfortable" | "standard" | "compact";
export type TaskView = "list" | "table" | "kanban" | "calendar";

interface UiState {
  /** Secciones del sidebar colapsadas (persistido en localStorage). */
  collapsedSections: Record<string, boolean>;
  toggleSection: (section: string) => void;
  /** Densidad de la interfaz: cómoda, estándar o compacta. */
  density: Density;
  setDensity: (density: Density) => void;
  /** Vista preferida de tareas por contexto ("global" o project id). */
  taskViews: Record<string, TaskView>;
  setTaskView: (context: string, view: TaskView) => void;
  /** Proyectos marcados como favoritos (ids). */
  favoriteProjects: number[];
  toggleFavoriteProject: (id: number) => void;
  /** Proyectos visitados recientemente (ids, más reciente primero). */
  recentProjects: number[];
  addRecentProject: (id: number) => void;
  /** Columnas ocultas en la vista de tabla de tareas. */
  hiddenTableColumns: string[];
  toggleTableColumn: (id: string) => void;
  /** Onboarding completado u omitido. */
  onboardingDone: boolean;
  setOnboardingDone: () => void;
  /** Checklist de primeros pasos (DashboardPage): flags persistidos. */
  onboarding: {
    dismissed: boolean;
    usedPalette: boolean;
    visitedKanban: boolean;
  };
  dismissOnboarding: () => void;
  /** Marca "usó la paleta Ctrl+K" — lo llama AppLayout cuando la paleta abre. */
  markPaletteUsed: () => void;
  /** Marca "visitó el kanban" — lo llama TasksPage cuando view === "kanban". */
  markKanbanVisited: () => void;
  /** Acento de color de la interfaz (preset en theme.ACCENTS). */
  accent: string;
  setAccent: (accent: string) => void;
  /** Módulos de Inicio ocultos por el usuario (personalización sencilla). */
  homeHiddenModules: string[];
  toggleHomeModule: (key: string) => void;
  /** Columnas kanban colapsadas, clave `${projectId ?? "global"}:${state}`. */
  kanbanCollapsed: Record<string, boolean>;
  toggleKanbanColumn: (key: string) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      collapsedSections: {},
      toggleSection: (section) =>
        set((s) => ({
          collapsedSections: {
            ...s.collapsedSections,
            [section]: !s.collapsedSections[section],
          },
        })),
      density: "standard",
      setDensity: (density) => set({ density }),
      taskViews: {},
      setTaskView: (context, view) =>
        set((s) => ({ taskViews: { ...s.taskViews, [context]: view } })),
      favoriteProjects: [],
      toggleFavoriteProject: (id) =>
        set((s) => ({
          favoriteProjects: s.favoriteProjects.includes(id)
            ? s.favoriteProjects.filter((p) => p !== id)
            : [...s.favoriteProjects, id],
        })),
      recentProjects: [],
      addRecentProject: (id) =>
        set((s) => ({
          recentProjects: [id, ...s.recentProjects.filter((p) => p !== id)].slice(0, 5),
        })),
      hiddenTableColumns: [],
      toggleTableColumn: (id) =>
        set((s) => ({
          hiddenTableColumns: s.hiddenTableColumns.includes(id)
            ? s.hiddenTableColumns.filter((c) => c !== id)
            : [...s.hiddenTableColumns, id],
        })),
      onboardingDone: false,
      setOnboardingDone: () => set({ onboardingDone: true }),
      onboarding: { dismissed: false, usedPalette: false, visitedKanban: false },
      dismissOnboarding: () =>
        set((s) => ({ onboarding: { ...s.onboarding, dismissed: true } })),
      markPaletteUsed: () =>
        set((s) =>
          s.onboarding.usedPalette
            ? s
            : { onboarding: { ...s.onboarding, usedPalette: true } },
        ),
      markKanbanVisited: () =>
        set((s) =>
          s.onboarding.visitedKanban
            ? s
            : { onboarding: { ...s.onboarding, visitedKanban: true } },
        ),
      accent: "indigo",
      setAccent: (accent) => set({ accent }),
      homeHiddenModules: [],
      toggleHomeModule: (key) =>
        set((s) => ({
          homeHiddenModules: s.homeHiddenModules.includes(key)
            ? s.homeHiddenModules.filter((k) => k !== key)
            : [...s.homeHiddenModules, key],
        })),
      kanbanCollapsed: {},
      toggleKanbanColumn: (key) =>
        set((s) => ({
          kanbanCollapsed: {
            ...s.kanbanCollapsed,
            [key]: !s.kanbanCollapsed[key],
          },
        })),
    }),
    { name: "todolist-ui" },
  ),
);
