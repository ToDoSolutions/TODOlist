import { api, tokenStorage } from "./client";
import type { User } from "../types";

export const authApi = {
  async login(email: string, password: string) {
    const { data } = await api.post("/auth/login/", { email, password });
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
  logout() {
    tokenStorage.clear();
  },
};
