/**
 * API client para el backend de TODOlist
 */
import axios from "axios";
import AsyncStorage from "@react-native-async-storage/async-storage";

const API_BASE_URL = "http://localhost:8000/api";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
});

// Interceptor: añadir JWT token a cada request
api.interceptors.request.use(
  async (config) => {
    const token = await AsyncStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor: refresh token si 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refreshToken = await AsyncStorage.getItem("refresh_token");
      if (refreshToken) {
        try {
          const resp = await axios.post(`${API_BASE_URL}/auth/refresh/`, {
            refresh: refreshToken,
          });
          const { access } = resp.data;
          await AsyncStorage.setItem("access_token", access);
          error.config.headers.Authorization = `Bearer ${access}`;
          return api(error.config);
        } catch (refreshError) {
          await AsyncStorage.multiRemove(["access_token", "refresh_token"]);
        }
      }
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login/", { email, password }).then((r) => r.data),
  register: (email: string, username: string, password: string) =>
    api.post("/auth/register/", { email, username, password }).then((r) => r.data),
};

export const tasksApi = {
  list: () => api.get("/tasks/").then((r) => r.data),
  create: (data: any) => api.post("/tasks/", data).then((r) => r.data),
  update: (id: number, data: any) => api.patch(`/tasks/${id}/`, data).then((r) => r.data),
  delete: (id: number) => api.delete(`/tasks/${id}/`).then((r) => r.data),
};

export const projectsApi = {
  list: () => api.get("/projects/").then((r) => r.data),
  create: (data: any) => api.post("/projects/", data).then((r) => r.data),
};
