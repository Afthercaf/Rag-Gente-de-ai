/**
 * API Client — Pizzería 220 AI
 *
 * Cliente HTTP con:
 * - Bearer token en endpoints protegidos
 * - Cookies HttpOnly habilitadas
 * - Refresh automático
 * - Cola de solicitudes durante refresh
 * - Manejo de errores normalizado
 * - Sin redirección física a /login
 */

import axios from "axios";

import {
  getAccessToken,
  getStoredUser,
  saveSession,
} from "../utils/session";

// ============================================================================
// CONFIGURACIÓN
// ============================================================================

const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  withCredentials: true,

  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
});

// ============================================================================
// ESTADO DE REFRESH
// ============================================================================

let isRefreshing = false;
let failedQueue = [];

function processQueue(
  error,
  token = null,
) {
  failedQueue.forEach(
    ({ resolve, reject }) => {
      if (error) {
        reject(error);
      } else {
        resolve(token);
      }
    },
  );

  failedQueue = [];
}

function notifyUnauthorized() {
  window.dispatchEvent(
    new CustomEvent(
      "p220:unauthorized",
    ),
  );
}

// ============================================================================
// NORMALIZACIÓN DE ERRORES
// ============================================================================

function getErrorMessage(error) {
  const data =
    error?.response?.data;

  const detail =
    data?.detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (
          typeof item === "string"
        ) {
          return item;
        }

        if (
          item &&
          typeof item === "object"
        ) {
          const location =
            Array.isArray(item.loc)
              ? item.loc.join(".")
              : "";

          const message =
            item.msg ||
            item.message ||
            "Error de validación";

          return location
            ? `${location}: ${message}`
            : message;
        }

        return null;
      })
      .filter(Boolean);

    if (messages.length > 0) {
      return messages.join("\n");
    }
  }

  if (
    detail &&
    typeof detail === "object"
  ) {
    return (
      detail.message ||
      detail.msg ||
      "Error al procesar la solicitud."
    );
  }

  if (
    typeof detail === "string"
  ) {
    return detail;
  }

  if (
    typeof data?.message === "string"
  ) {
    return data.message;
  }

  if (
    typeof data?.error === "string"
  ) {
    return data.error;
  }

  if (error?.message) {
    return error.message;
  }

  return "Error de comunicación con el servidor.";
}

function normalizeError(error) {
  if (
    error instanceof Error &&
    error.normalized === true
  ) {
    return error;
  }

  const normalized =
    new Error(
      getErrorMessage(error),
    );

  normalized.status =
    error?.response?.status;

  normalized.data =
    error?.response?.data;

  normalized.originalError =
    error;

  normalized.normalized = true;

  return normalized;
}

// ============================================================================
// INTERCEPTOR DE SOLICITUDES
// ============================================================================

api.interceptors.request.use(
  (config) => {
    const token =
      getAccessToken();

    /*
     * El backend protege /chat y otros endpoints mediante:
     *
     * Authorization: Bearer <access_token>
     */
    if (token) {
      config.headers =
        config.headers || {};

      config.headers.Authorization =
        `Bearer ${token}`;
    }

    /*
     * No forzar application/json cuando el body es FormData.
     * Axios necesita generar el boundary automáticamente.
     */
    if (
      config.data instanceof FormData
    ) {
      delete config.headers[
        "Content-Type"
      ];

      delete config.headers[
        "content-type"
      ];
    }

    return config;
  },

  (error) =>
    Promise.reject(
      normalizeError(error),
    ),
);

// ============================================================================
// INTERCEPTOR DE RESPUESTAS
// ============================================================================

api.interceptors.response.use(
  (response) => response,

  async (error) => {
    const originalRequest =
      error?.config;

    if (!originalRequest) {
      return Promise.reject(
        normalizeError(error),
      );
    }

    const status =
      error?.response?.status;

    const requestUrl =
      String(
        originalRequest.url || "",
      );

    const isLoginRequest =
      requestUrl.includes(
        "/auth/login",
      );

    const isRegisterRequest =
      requestUrl.includes(
        "/auth/register",
      );

    const isRefreshRequest =
      requestUrl.includes(
        "/auth/refresh",
      );

    const isLogoutRequest =
      requestUrl.includes(
        "/auth/logout",
      );

    /*
     * No intentar refresh cuando:
     * - el error no es 401;
     * - es login;
     * - es registro;
     * - es refresh;
     * - es logout;
     * - ya fue reintentada.
     */
    if (
      status !== 401 ||
      isLoginRequest ||
      isRegisterRequest ||
      isRefreshRequest ||
      isLogoutRequest ||
      originalRequest._retry
    ) {
      return Promise.reject(
        normalizeError(error),
      );
    }

    /*
     * Si otro refresh está activo,
     * la solicitud queda en espera.
     */
    if (isRefreshing) {
      return new Promise(
        (resolve, reject) => {
          failedQueue.push({
            resolve,
            reject,
          });
        },
      )
        .then((newToken) => {
          originalRequest.headers =
            originalRequest.headers || {};

          if (newToken) {
            originalRequest
              .headers
              .Authorization =
              `Bearer ${newToken}`;
          }

          return api(
            originalRequest,
          );
        })
        .catch((queueError) =>
          Promise.reject(
            normalizeError(
              queueError,
            ),
          ),
        );
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      /*
       * El refresh token puede viajar en cookie HttpOnly.
       * También conservamos el Bearer actual por compatibilidad.
       */
      const refreshResponse =
        await api.post(
          "/auth/refresh",
          {},
        );

      const newAccessToken =
        refreshResponse
          ?.data
          ?.access_token ||
        refreshResponse
          ?.data
          ?.token;

      if (!newAccessToken) {
        throw new Error(
          "El servidor no devolvió un nuevo access token.",
        );
      }

      saveSession({
        accessToken:
          newAccessToken,

        user:
          refreshResponse
            ?.data
            ?.user ||
          getStoredUser(),
      });

      originalRequest.headers =
        originalRequest.headers || {};

      originalRequest
        .headers
        .Authorization =
        `Bearer ${newAccessToken}`;

      processQueue(
        null,
        newAccessToken,
      );

      return api(
        originalRequest,
      );
    } catch (refreshError) {
      processQueue(
        refreshError,
      );

      notifyUnauthorized();

      return Promise.reject(
        normalizeError(
          refreshError,
        ),
      );
    } finally {
      isRefreshing = false;
    }
  },
);

// ============================================================================
// AUTENTICACIÓN
// ============================================================================

export async function login(
  gmail,
  password,
) {
  try {
    const response =
      await api.post(
        "/auth/login",
        {
          gmail,
          password,
        },
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function register(
  userData,
) {
  try {
    const response =
      await api.post(
        "/auth/register",
        userData,
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function logout() {
  try {
    const response =
      await api.post(
        "/auth/logout",
        {},
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function getMe() {
  try {
    const response =
      await api.get(
        "/auth/me",
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function refreshToken() {
  try {
    const response =
      await api.post(
        "/auth/refresh",
        {},
      );

    const newAccessToken =
      response
        ?.data
        ?.access_token ||
      response
        ?.data
        ?.token;

    if (newAccessToken) {
      saveSession({
        accessToken:
          newAccessToken,

        user:
          response
            ?.data
            ?.user ||
          getStoredUser(),
      });
    }

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

// ============================================================================
// CHAT
// ============================================================================

export async function sendMessage(
  message,
  options = {},
) {
  try {
    const response =
      await api.post(
        "/chat",
        {
          message,

          use_cache:
            options.useCache ??
            true,

          save_history:
            options.saveHistory ??
            true,
        },
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function getChatHistory(
  limit = 50,
) {
  try {
    const response =
      await api.get(
        "/chat/history",
        {
          params: {
            limit,
          },
        },
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function deleteChatHistory() {
  try {
    const response =
      await api.delete(
        "/chat/history",
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

// ============================================================================
// ÓRDENES
// ============================================================================

export async function createOrder(
  orderData,
) {
  try {
    const response =
      await api.post(
        "/order",
        orderData,
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function getOrderStatus(
  orderId,
) {
  try {
    const response =
      await api.get(
        `/order/${orderId}/status`,
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function cancelOrder(
  orderId,
) {
  try {
    const response =
      await api.post(
        `/order/${orderId}/cancel`,
        {},
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

// ============================================================================
// VOZ
// ============================================================================

export async function transcribeAudio(
  audioBlob,
  language = "es-ES",
) {
  const formData =
    new FormData();

  formData.append(
    "audio",
    audioBlob,
    "recording.webm",
  );

  formData.append(
    "language",
    language,
  );

  try {
    const response =
      await api.post(
        "/voice/transcribe",
        formData,
        {
          timeout: 60000,
        },
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function getVoiceHistory(
  limit = 10,
) {
  try {
    const response =
      await api.get(
        "/voice/history",
        {
          params: {
            limit,
          },
        },
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

// ============================================================================
// MAPAS
// ============================================================================

export async function reverseGeocode(
  lat,
  lng,
) {
  try {
    const response =
      await api.get(
        "/maps/reverse",
        {
          params: {
            lat,
            lng,
          },
        },
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function searchAddress(
  query,
) {
  try {
    const response =
      await api.get(
        "/maps/search",
        {
          params: {
            q: query,
          },
        },
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function getStaticMap(
  lat,
  lng,
  zoom = 16,
) {
  try {
    const response =
      await api.get(
        "/maps/static",
        {
          params: {
            lat,
            lng,
            zoom,
          },

          responseType:
            "blob",
        },
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

// ============================================================================
// CACHÉ
// ============================================================================

export async function getCacheStats() {
  try {
    const response =
      await api.get(
        "/cache/stats",
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function clearCache() {
  try {
    const response =
      await api.post(
        "/cache/clear",
        {},
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

// ============================================================================
// SALUD
// ============================================================================

export async function healthCheck() {
  try {
    const response =
      await api.get(
        "/health",
      );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export default api;