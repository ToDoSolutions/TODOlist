import { createContext, useContext, useState, ReactNode } from "react";
import { useUiStore } from "../store/uiStore";

export interface SelectedProject {
  id: number;
  name: string;
  color: string;
}

interface ProjectContextValue {
  project: SelectedProject | null;
  setProject: (p: SelectedProject | null) => void;
  clearProject: () => void;
}

const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [project, setProjectState] = useState<SelectedProject | null>(null);

  const setProject = (p: SelectedProject | null) => {
    setProjectState(p);
    if (p) {
      localStorage.setItem("selectedProject", JSON.stringify(p));
      useUiStore.getState().addRecentProject(p.id);
    } else {
      localStorage.removeItem("selectedProject");
    }
  };

  const clearProject = () => {
    setProjectState(null);
    localStorage.removeItem("selectedProject");
  };

  // Restore from localStorage on mount
  useState(() => {
    const saved = localStorage.getItem("selectedProject");
    if (saved) {
      try {
        setProjectState(JSON.parse(saved));
      } catch {
        localStorage.removeItem("selectedProject");
      }
    }
  });

  return (
    <ProjectContext.Provider value={{ project, setProject, clearProject }}>
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProject must be used within ProjectProvider");
  return ctx;
}
