import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import axiosRetry from "axios-retry";
import { env } from "../env";

const API_URL = env.VITE_API_URL;

const CSRF_COOKIE = "todolist_csrf";

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

// Los tokens JWT viven en cookies httpOnly (no accesibles desde JS).
// tokenStorage se mantiene solo para tokens explícitos de flujos legacy
// (p.ej. saveTokens tras OAuth); no es la vía principal.
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

export const api = axios.create({ baseURL: API_URL, withCredentials: true });

// Reintentos ante fallos transitorios de red/5xx (no reintenta 4xx).
axiosRetry(api, {
  retries: 2,
  retryDelay: axiosRetry.exponentialDelay,
  retryCondition: (err) =>
    axiosRetry.isNetworkOrIdempotentRequestError(err) ||
    err.response?.status === 502 ||
    err.response?.status === 503 ||
    err.response?.status === 504,
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  // Double-submit CSRF: los métodos no seguros deben devolver la cookie
  // todolist_csrf como header X-CSRFToken cuando la auth es por cookie.
  const method = (config.method || "get").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
    const csrf = getCookie(CSRF_COOKIE);
    if (csrf) config.headers["X-CSRFToken"] = csrf;
  }
  // Bearer explícito si existe token almacenado (flujo legacy/OAuth)
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
    // Refresh via cookie httpOnly: el body puede ir vacío.
    const hasSession = getCookie(CSRF_COOKIE) || tokenStorage.getRefresh();
    if (error.response?.status === 401 && !original._retry && hasSession) {
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
        const refresh = tokenStorage.getRefresh();
        const { data } = await axios.post(
          `${API_URL}/auth/refresh/`,
          refresh ? { refresh } : {},
          { withCredentials: true },
        );
        if (data.access && data.refresh) {
          tokenStorage.set(data.access, data.refresh);
        }
        queue.forEach((fn) => fn());
        queue = [];
        return api(original);
      } catch (e) {
        queue = [];
        tokenStorage.clear();
        window.location.href = `/session-expired?next=${encodeURIComponent(
          window.location.pathname + window.location.search,
        )}`;
        return Promise.reject(e);
      } finally {
        isRefreshing = false;
      }
    }
    // 403 en una lectura = el usuario no tiene acceso al recurso de la
    // página actual → ForbiddenPage. Las mutaciones devuelven el error
    // al caller para que la UI muestre el motivo en línea.
    if (
      error.response?.status === 403 &&
      (original.method || "get").toLowerCase() === "get" &&
      window.location.pathname !== "/app/403"
    ) {
      window.location.href = "/app/403";
    }
    return Promise.reject(error);
  },
);
