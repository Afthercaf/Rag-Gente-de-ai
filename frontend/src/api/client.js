/**
 * API Client — Pizzería 220 AI
 *
 * Cliente HTTP con manejo automático de refresh tokens.
 *
 * Características:
 * - Interceptor de respuestas 401
 * - Refresh automático
 * - Cookies HttpOnly
 * - Cola de solicitudes pendientes durante el refresh
 * - Sin redirecciones directas a /login
 */

import axios from "axios";

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
// ESTADO DEL REFRESH
// ============================================================================

let isRefreshing = false;
let failedQueue = [];

function processQueue(
  error,
  token = null,
) {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else {
      promise.resolve(token);
    }
  });

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
  const responseData =
    error?.response?.data;

  const detail =
    responseData?.detail;

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

  if (error?.message) {
    return error.message;
  }

  return "Error de comunicación con el servidor.";
}

function normalizeError(error) {
  const normalizedError =
    new Error(
      getErrorMessage(error),
    );

  normalizedError.status =
    error?.response?.status;

  normalizedError.data =
    error?.response?.data;

  normalizedError.originalError =
    error;

  return normalizedError;
}

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

    const isAuthRequest =
      requestUrl.includes(
        "/auth/login",
      ) ||
      requestUrl.includes(
        "/auth/register",
      );

    const isRefreshRequest =
      requestUrl.includes(
        "/auth/refresh",
      );

    /*
     * Solo se intenta refresh cuando:
     * - el backend responde 401;
     * - no es login o registro;
     * - no es la propia ruta de refresh;
     * - la solicitud no se ha reintentado.
     */
    if (
      status !== 401 ||
      isAuthRequest ||
      isRefreshRequest ||
      originalRequest._retry
    ) {
      return Promise.reject(
        normalizeError(error),
      );
    }

    /*
     * Si ya existe un refresh activo, esta solicitud
     * queda en espera.
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
        .then(() =>
          api(originalRequest),
        )
        .catch((queueError) =>
          Promise.reject(
            normalizeError(queueError),
          ),
        );
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      /*
       * El refresh usa la cookie HttpOnly.
       * No se envía token manualmente.
       */
      await api.post(
        "/auth/refresh",
      );

      processQueue(null);

      return api(originalRequest);
    } catch (refreshError) {
      processQueue(
        refreshError,
      );

      /*
       * No se utiliza:
       *
       * window.location.href = "/login";
       *
       * porque Render puede responder Not Found
       * al acceder directamente a esa ruta.
       */
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
    const response = await api.post(
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
    const response = await api.post(
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
    const response = await api.post(
      "/auth/logout",
    );

    return response.data;
  } catch (error) {
    /*
     * Aunque el backend falle, notificamos al frontend
     * para limpiar la sesión local.
     */
    throw normalizeError(error);
  }
}

export async function getMe() {
  try {
    const response = await api.get(
      "/auth/me",
    );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function refreshToken() {
  try {
    const response = await api.post(
      "/auth/refresh",
    );

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
    const response = await api.post(
      "/chat",
      {
        message,
        use_cache:
          options.useCache ?? true,
        save_history:
          options.saveHistory ?? true,
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
    const response = await api.get(
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
    const response = await api.post(
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
    const response = await api.get(
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
    const response = await api.post(
      `/order/${orderId}/cancel`,
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
    /*
     * No se define manualmente Content-Type.
     * Axios agrega multipart/form-data junto con
     * el boundary correcto.
     */
    const response = await api.post(
      "/voice/transcribe",
      formData,
      {
        timeout: 60000,

        headers: {
          "Content-Type": undefined,
        },
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
    const response = await api.get(
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
    const response = await api.get(
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
    const response = await api.get(
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
    const response = await api.get(
      "/maps/static",
      {
        params: {
          lat,
          lng,
          zoom,
        },

        responseType: "blob",
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
    const response = await api.get(
      "/cache/stats",
    );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function clearCache() {
  try {
    const response = await api.post(
      "/cache/clear",
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
    const response = await api.get(
      "/health",
    );

    return response.data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export default api;