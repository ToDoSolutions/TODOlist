import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Typography,
} from "@mui/material";
import { Box } from "@mui/material";
import { useTranslation } from "react-i18next";

const isMac = typeof navigator !== "undefined" && /Mac/i.test(navigator.platform);
const MOD = isMac ? "⌘" : "Ctrl";

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <Box
      component="kbd"
      sx={{
        px: 0.75,
        py: 0.25,
        border: 1,
        borderColor: "divider",
        borderBottomWidth: 2,
        borderRadius: 0.75,
        fontSize: 12,
        fontFamily: "monospace",
        bgcolor: "action.hover",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </Box>
  );
}

/** Referencia de atajos de teclado. Se abre con Shift+? o desde el menú de ayuda. */
export default function ShortcutsDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const SHORTCUTS: { keys: React.ReactNode; action: string; context: string }[] = [
    {
      keys: (
        <>
          <Kbd>{MOD}</Kbd> + <Kbd>K</Kbd>
        </>
      ),
      action: t("p.shell.ui.shortcuts.openPalette"),
      context: t("p.shell.ui.shortcuts.ctxGlobal"),
    },
    {
      keys: (
        <>
          <Kbd>Shift</Kbd> + <Kbd>?</Kbd>
        </>
      ),
      action: t("p.shell.ui.shortcuts.showHelp"),
      context: t("p.shell.ui.shortcuts.ctxGlobal"),
    },
    {
      keys: (
        <>
          <Kbd>↑</Kbd> / <Kbd>↓</Kbd>
        </>
      ),
      action: t("p.shell.ui.shortcuts.navigateResults"),
      context: t("p.shell.ui.shortcuts.ctxPalette"),
    },
    {
      keys: <Kbd>Enter</Kbd>,
      action: t("p.shell.ui.shortcuts.openSelected"),
      context: t("p.shell.ui.shortcuts.ctxPaletteDialogs"),
    },
    {
      keys: (
        <>
          <Kbd>J</Kbd> / <Kbd>K</Kbd>
        </>
      ),
      action: t("p.shell.ui.shortcuts.listNav"),
      context: t("p.shell.ui.shortcuts.ctxTaskList"),
    },
    {
      keys: <Kbd>X</Kbd>,
      action: t("p.shell.ui.shortcuts.listSelect"),
      context: t("p.shell.ui.shortcuts.ctxTaskList"),
    },
    {
      keys: (
        <>
          <Kbd>E</Kbd> / <Kbd>Enter</Kbd>
        </>
      ),
      action: t("p.shell.ui.shortcuts.listOpen"),
      context: t("p.shell.ui.shortcuts.ctxTaskList"),
    },
    {
      keys: <Kbd>C</Kbd>,
      action: t("p.shell.ui.shortcuts.listNew"),
      context: t("p.shell.ui.shortcuts.ctxTaskList"),
    },
    {
      keys: <Kbd>Esc</Kbd>,
      action: t("p.shell.ui.shortcuts.close"),
      context: t("p.shell.ui.shortcuts.ctxGlobal"),
    },
  ];

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{t("p.shell.ui.shortcuts.title")}</DialogTitle>
      <DialogContent>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{t("p.shell.ui.shortcuts.colShortcut")}</TableCell>
              <TableCell>{t("p.shell.ui.shortcuts.colAction")}</TableCell>
              <TableCell>{t("p.shell.ui.shortcuts.colContext")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {SHORTCUTS.map((s, i) => (
              <TableRow key={i}>
                <TableCell>{s.keys}</TableCell>
                <TableCell>
                  <Typography variant="body2">{s.action}</Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="caption" color="text.secondary">
                    {s.context}
                  </Typography>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("common.close")}</Button>
      </DialogActions>
    </Dialog>
  );
}
