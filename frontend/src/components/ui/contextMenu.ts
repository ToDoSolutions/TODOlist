import { useCallback, useState } from "react";

export interface ContextMenuState<T> {
  /** Posición del menú (anchorPosition para MUI Menu). */
  mouseX: number;
  mouseY: number;
  /** Entidad sobre la que se abrió el menú. */
  target: T;
}

/**
 * Estado compartido para menús contextuales (clic derecho) — patrón
 * Todoist/Linear/ClickUp. Uso:
 *
 *   const menu = useContextMenu<Task>();
 *   <Box onContextMenu={menu.openFor(task)} />
 *   <Menu open={!!menu.state} onClose={menu.close}
 *         anchorReference="anchorPosition"
 *         anchorPosition={menu.state && { top: menu.state.mouseY, left: menu.state.mouseX }}>
 *     <MenuItem onClick={() => { act(menu.state!.target); menu.close(); }} />
 *   </Menu>
 */
export function useContextMenu<T>() {
  const [state, setState] = useState<ContextMenuState<T> | null>(null);

  const openFor = useCallback(
    (target: T) => (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setState({ mouseX: e.clientX + 2, mouseY: e.clientY - 6, target });
    },
    [],
  );

  const close = useCallback(() => setState(null), []);

  return { state, openFor, close };
}
