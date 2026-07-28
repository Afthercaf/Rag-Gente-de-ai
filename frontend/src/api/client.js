/**
 * API Client — Pizzería 220 AI
 *
 * Características:
 * - Axios centralizado;
 * - access token en cookie HttpOnly (nombre depende de ENV: __Host-access_token en prod,
 *   access_token en desarrollo);
 * - cookies HttpOnly habilitadas;
 * - renovación automática de sesión;
 * - cola de solicitudes durante refresh;
 * - manejo consistente de errores;
 * - sin navegación física a /login.
 */

import axios from "axios";

import {
  clearSession,
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
    Accept:
      "application/json",

    "Content-Type":
      "application/json",
  },
});

// ============================================================================
// ESTADO DEL REFRESH
// ============================================================================

let isRefreshing = false;

let failedQueue = [];

/**
 * Resuelve o rechaza las solicitudes que quedaron esperando
 * mientras se renovaba el token.
 */
function processQueue(
  error,
) {
  failedQueue.forEach(
    ({
      resolve,
      reject,
    }) => {
      if (error) {
        reject(error);
      } else {
        resolve();
      }
    },
  );

  failedQueue = [];
}

/**
 * Informa a React que la sesión dejó de ser válida.
 */
function notifyUnauthorized() {
  window.dispatchEvent(
    new CustomEvent(
      "p220:unauthorized",
    ),
  );
}

// ============================================================================
// ERRORES
// ============================================================================

function getErrorMessage(
  error,
) {
  const responseData =
    error?.response?.data;

  const detail =
    responseData?.detail;

  if (
    Array.isArray(detail)
  ) {
    const messages =
      detail
        .map((item) => {
          if (
            typeof item ===
            "string"
          ) {
            return item;
          }

          if (
            item &&
            typeof item ===
            "object"
          ) {
            const location =
              Array.isArray(
                item.loc,
              )
                ? item.loc.join(
                    ".",
                  )
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

    if (
      messages.length > 0
    ) {
      return messages.join(
        "\n",
      );
    }
  }

  if (
    detail &&
    typeof detail ===
      "object"
  ) {
    return (
      detail.message ||
      detail.msg ||
      "Error al procesar la solicitud."
    );
  }

  if (
    typeof detail ===
    "string"
  ) {
    return detail;
  }

  if (
    typeof responseData?.message ===
    "string"
  ) {
    return responseData.message;
  }

  if (
    typeof responseData?.error ===
    "string"
  ) {
    return responseData.error;
  }

  if (
    typeof error?.message ===
    "string"
  ) {
    return error.message;
  }

  return "Error de comunicación con el servidor.";
}

function normalizeError(
  error,
) {
  if (
    error instanceof Error &&
    error.normalized === true
  ) {
    return error;
  }

  const normalizedError =
    new Error(
      getErrorMessage(
        error,
      ),
    );

  normalizedError.status =
    error?.response?.status;

  normalizedError.data =
    error?.response?.data;

  normalizedError.originalError =
    error;

  normalizedError.normalized =
    true;

  return normalizedError;
}

// ============================================================================
// INTERCEPTOR DE SOLICITUDES
// ============================================================================

api.interceptors.request.use(
  (config) => {
    config.headers =
      config.headers || {};

    // ✅ M-01 FIX: No enviar Authorization Bearer desde sessionStorage.
    // La autenticación viaja en cookie HttpOnly (access_token en dev,
    // __Host-access_token en producción).
    delete config.headers.Authorization;
    delete config.headers.authorization;

    // ✅ C-01 FIX: Señal anti-CSRF para métodos mutantes.
    const method = (
      config.method || ""
    ).toUpperCase();
    if (
      ["POST", "PUT", "PATCH", "DELETE"].includes(
        method,
      )
    ) {
      config.headers["X-Requested-With"] =
        "XMLHttpRequest";
    }

    /**
     * Axios debe generar automáticamente el boundary
     * cuando se envía FormData.
     */
    if (
      config.data instanceof
      FormData
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
      normalizeError(
        error,
      ),
    ),
);

// ============================================================================
// INTERCEPTOR DE RESPUESTAS
// ============================================================================

api.interceptors.response.use(
  (response) =>
    response,

  async (error) => {
    const originalRequest =
      error?.config;

    if (!originalRequest) {
      return Promise.reject(
        normalizeError(
          error,
        ),
      );
    }

    const status =
      error?.response?.status;

    const requestUrl =
      String(
        originalRequest.url ||
        "",
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

    /**
     * No renovar cuando:
     * - no es 401;
     * - es login;
     * - es registro;
     * - es refresh;
     * - es logout;
     * - ya se reintentó.
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
        normalizeError(
          error,
        ),
      );
    }

    /**
     * Otra solicitud ya está renovando el token.
     */
    if (isRefreshing) {
      return new Promise(
        (
          resolve,
          reject,
        ) => {
          failedQueue.push({
            resolve,
            reject,
          });
        },
      )
        .then(
          () => {
            // ✅ M-01 FIX: Reintentar con la cookie HttpOnly recién rotada.
            return api(
              originalRequest,
            );
          },
        )
        .catch(
          (
            queueError,
          ) =>
            Promise.reject(
              normalizeError(
                queueError,
              ),
            ),
        );
    }

    originalRequest._retry =
      true;

    isRefreshing = true;

    try {
      /**
       * El refresh token debe viajar en cookie HttpOnly.
       * Se envía un objeto vacío para conservar Content-Type JSON
       * y evitar errores 415 en middlewares estrictos.
       */
      const refreshResponse =
        await api.post(
          "/auth/refresh",
          {},
        );

      const refreshedUser =
        refreshResponse
          ?.data
          ?.user;

      // ✅ M-01 FIX: No almacenar access token en JS.
      saveSession({
        user:
          refreshedUser ||
          getStoredUser(),
      });

      // ✅ M-01 FIX: No enviar Authorization Bearer; la cookie ya se actualizó
      // con el nombre correspondiente al entorno.
      processQueue(null);

      return api(
        originalRequest,
      );
    } catch (
      refreshError
    ) {
      processQueue(
        refreshError,
      );

      clearSession();

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
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
  }
}

export async function refreshToken() {
  try {
    const response =
      await api.post(
        "/auth/refresh",
        {},
      );

    // ✅ M-01 FIX: El access token viaja en cookie HttpOnly.
    saveSession({
      user:
        response
          ?.data
          ?.user ||
        getStoredUser(),
    });

    return response.data;
  } catch (error) {
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
  }
}

export async function getAvailableExtras() {
  try {
    const response = await api.get("/chat/extras");
    return Array.isArray(response.data?.extras)
      ? response.data.extras
      : [];
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
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
  }
}

// ============================================================================
// VOZ
// ============================================================================

export async function transcribeAudio(
  audioBlob,
  language = "es-MX",
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
          timeout:
            60000,
        },
      );

    return response.data;
  } catch (error) {
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
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
            q:
              query,
          },
        },
      );

    return response.data;
  } catch (error) {
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
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
    throw normalizeError(
      error,
    );
  }
}

export default api;
