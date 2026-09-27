// Estado del command palette global (Ctrl+K / Cmd+K).
import { useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";

export function useCommandPalette() {
  const [open, setOpen] = useState(false);
  useHotkeys("ctrl+k,meta+k", (e) => {
    e.preventDefault();
    setOpen((o) => !o);
  });
  return { open, setOpen };
}
