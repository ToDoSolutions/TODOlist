import { api, tokenStorage } from "./client";
import type { User } from "../types";

export const authApi = {
  async login(email: string, password: string, totpCode?: string) {
    const { data } = await api.post("/auth/login/", {
      email,
      password,
      ...(totpCode ? { totp_code: totpCode } : {}),
    });
    tokenStorage.set(data.access, data.refresh);
    return data;
  },
  async register(payload: {
    email: string;
    username: string;
    password: string;
    password2: string;
  }) {
    const { data } = await api.post("/auth/register/", payload);
    return data as User;
  },
  async me() {
    const { data } = await api.get<User>("/auth/me/");
    return data;
  },
  async updateMe(payload: Partial<Pick<User, "username" | "timezone" | "locale">>) {
    const { data } = await api.patch<User>("/auth/me/", payload);
    return data;
  },
  async changePassword(currentPassword: string, newPassword: string) {
    const { data } = await api.post("/auth/change-password/", {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return data;
  },
  async sendVerificationEmail() {
    const { data } = await api.post("/auth/send-verification/");
    return data as { message: string };
  },
  async verifyEmail(uid: string, token: string) {
    const { data } = await api.post("/auth/verify-email/", { uid, token });
    return data as { message: string };
  },
  async requestPasswordReset(email: string) {
    const { data } = await api.post("/auth/password-reset/", { email });
    return data as { message: string };
  },
  async confirmPasswordReset(uid: string, token: string, newPassword: string) {
    const { data } = await api.post("/auth/password-reset/confirm/", {
      uid,
      token,
      new_password: newPassword,
    });
    return data as { message: string };
  },
  async logout() {
    // Invalidar el refresh token en el backend (blacklist)
    const refresh = tokenStorage.getRefresh();
    try {
      if (refresh) {
        await api.post("/auth/logout/", { refresh });
      }
    } catch {
      // Logout idempotente: limpiar siempre el almacenamiento local
    }
    tokenStorage.clear();
  },
};
