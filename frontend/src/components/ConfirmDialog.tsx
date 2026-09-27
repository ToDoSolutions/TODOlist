import { createContext, useCallback, useContext, useRef, useState } from "react";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  TextField,
} from "@mui/material";
import { useTranslation } from "react-i18next";

interface ConfirmOptions {
  title?: string;
  confirmLabel?: string;
  /** Si se indica, el usuario debe escribir este texto para confirmar
   *  (para acciones destructivas irreversibles). */
  requireText?: string;
  danger?: boolean;
}

type Resolver = (value: boolean) => void;

const ConfirmContext = createContext<
  (message: string, opts?: ConfirmOptions) => Promise<boolean>
>(() => Promise.resolve(false));

export function useConfirm() {
  return useContext(ConfirmContext);
}

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [opts, setOpts] = useState<ConfirmOptions>({});
  const [typed, setTyped] = useState("");
  const resolverRef = useRef<Resolver>(() => {});

  const confirm = useCallback(
    (msg: string, o: ConfirmOptions = {}) =>
      new Promise<boolean>((resolve) => {
        setMessage(msg);
        setOpts(o);
        setTyped("");
        resolverRef.current = resolve;
        setOpen(true);
      }),
    [],
  );

  const close = (value: boolean) => {
    resolverRef.current(value);
    resolverRef.current = () => {};
    setOpen(false);
  };

  const needsTyping = !!opts.requireText;
  const canConfirm = !needsTyping || typed.trim() === opts.requireText;

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Dialog
        open={open}
        onClose={() => close(false)}
        maxWidth="xs"
        fullWidth
        aria-labelledby="confirm-dialog-title"
      >
        <DialogTitle id="confirm-dialog-title">
          {opts.title || t("p.shell.ui.confirm.title")}
        </DialogTitle>
        <DialogContent>
          <DialogContentText>{message}</DialogContentText>
          {needsTyping && (
            <TextField
              autoFocus
              fullWidth
              size="small"
              sx={{ mt: 2 }}
              placeholder={t("p.shell.ui.confirm.typeToConfirm", {
                text: opts.requireText,
              })}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              inputProps={{ "aria-label": t("p.shell.ui.confirm.typedAriaLabel") }}
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => close(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            color={opts.danger === false ? "primary" : "error"}
            disabled={!canConfirm}
            onClick={() => close(true)}
          >
            {opts.confirmLabel || t("common.confirm")}
          </Button>
        </DialogActions>
      </Dialog>
    </ConfirmContext.Provider>
  );
}
