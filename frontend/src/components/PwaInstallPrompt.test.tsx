import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material";
import { createElement, type ReactNode } from "react";
import PwaInstallPrompt from "./PwaInstallPrompt";

function wrapper({ children }: { children: ReactNode }) {
  return createElement(ThemeProvider, { theme: createTheme() }, children);
}

function fireInstallEvent(prompt = vi.fn().mockResolvedValue(undefined)) {
  const e = new Event("beforeinstallprompt") as Event & {
    prompt: () => Promise<void>;
    userChoice: Promise<{ outcome: string }>;
  };
  e.preventDefault = vi.fn();
  e.prompt = prompt;
  e.userChoice = Promise.resolve({ outcome: "accepted" });
  window.dispatchEvent(e);
}

describe("PwaInstallPrompt", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "onLine", {
      value: true,
      writable: true,
      configurable: true,
    });
  });

  it("beforeinstallprompt muestra el snackbar de instalar", async () => {
    render(<PwaInstallPrompt />, { wrapper });
    fireInstallEvent();
    await waitFor(() =>
      expect(screen.getByText(/Instala TODOlist como app/i)).toBeTruthy(),
    );
  });

  it("click en Instalar llama a prompt() del evento", async () => {
    const prompt = vi.fn().mockResolvedValue(undefined);
    render(<PwaInstallPrompt />, { wrapper });
    fireInstallEvent(prompt);
    const btn = await screen.findByRole("button", { name: /instalar/i });
    fireEvent.click(btn);
    await waitFor(() => expect(prompt).toHaveBeenCalled());
  });

  it("la X cierra el snackbar sin instalar", async () => {
    const prompt = vi.fn();
    render(<PwaInstallPrompt />, { wrapper });
    fireInstallEvent(prompt);
    await screen.findByText(/Instala TODOlist/i);
    const closeButtons = screen.getAllByRole("button");
    // El último IconButton es la X de cierre
    fireEvent.click(closeButtons[closeButtons.length - 1]!);
    await waitFor(() => expect(screen.queryByText(/Instala TODOlist/i)).toBeNull());
    expect(prompt).not.toHaveBeenCalled();
  });

  it("evento offline muestra el banner de sin conexión", async () => {
    render(<PwaInstallPrompt />, { wrapper });
    window.dispatchEvent(new Event("offline"));
    await waitFor(() => expect(screen.getByText(/Sin conexión/i)).toBeTruthy());
  });

  it("evento online oculta el banner", async () => {
    render(<PwaInstallPrompt />, { wrapper });
    window.dispatchEvent(new Event("offline"));
    await waitFor(() => screen.getByText(/Sin conexión/i));
    window.dispatchEvent(new Event("online"));
    await waitFor(() => expect(screen.queryByText(/Sin conexión/i)).toBeNull());
  });
});
