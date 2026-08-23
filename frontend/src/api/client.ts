import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const ACCESS_KEY = "todolist.access";
const REFRESH_KEY = "todolist.refresh";

export const tokenStorage = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access: string, refresh: string) => {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStorage.getAccess();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isRefreshing = false;
let queue: Array<() => void> = [];

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };
    if (
      error.response?.status === 401 &&
      !original._retry &&
      tokenStorage.getRefresh()
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          queue.push(() => {
            original._retry = true;
            api(original).then(resolve).catch(reject);
          });
        });
      }
      original._retry = true;
      isRefreshing = true;
      try {
        const refresh = tokenStorage.getRefresh()!;
        const { data } = await axios.post(`${API_URL}/auth/refresh/`, {
          refresh,
        });
        tokenStorage.set(data.access, data.refresh ?? refresh);
        queue.forEach((fn) => fn());
        queue = [];
        return api(original);
      } catch (e) {
        queue = [];
        tokenStorage.clear();
        window.location.href = "/login";
        return Promise.reject(e);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);
