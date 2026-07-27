import {
  clearSession,
  getAccessToken,
} from "../utils/session";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8000"
).replace(/\/+$/, "");

function formatValidationDetail(detail) {
  if (!Array.isArray(detail)) {
    return null;
  }

  return detail
    .map((item) => {
      const path = Array.isArray(item?.loc)
        ? item.loc
            .filter(
              (part) =>
                part !== "body" &&
                part !== "query",
            )
            .join(".")
        : "";

      const message =
        typeof item?.msg === "string"
          ? item.msg
          : "Valor inválido";

      return path
        ? `${path}: ${message}`
        : message;
    })
    .filter(Boolean)
    .join("\n");
}

export function getApiErrorMessage(
  data,
  fallback = "No fue posible procesar la solicitud",
) {
  const validationMessage =
    formatValidationDetail(data?.detail);

  if (validationMessage) {
    return validationMessage;
  }

  if (typeof data?.detail === "string") {
    return data.detail;
  }

  if (typeof data?.message === "string") {
    return data.message;
  }

  if (typeof data?.error === "string") {
    return data.error;
  }

  return fallback;
}

function buildHeaders({
  body,
  headers = {},
  authenticated = true,
}) {
  const nextHeaders = new Headers(headers);

  if (
    body !== undefined &&
    !(body instanceof FormData)
  ) {
    nextHeaders.set(
      "Content-Type",
      "application/json",
    );
  }

  if (authenticated) {
    const token = getAccessToken();

    if (!token) {
      throw new Error(
        "Tu sesión terminó. Inicia sesión nuevamente.",
      );
    }

    nextHeaders.set(
      "Authorization",
      `Bearer ${token}`,
    );
  }

  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    nextHeaders.set(
      "X-Request-ID",
      crypto.randomUUID(),
    );
  }

  return nextHeaders;
}

async function readResponseData(response) {
  const contentType =
    response.headers.get("content-type") || "";

  if (
    contentType.includes("application/json")
  ) {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }

  try {
    return {
      detail: await response.text(),
    };
  } catch {
    return {};
  }
}

async function validateResponse(response) {
  const data = await readResponseData(response);

  if (response.status === 401) {
    clearSession();

    window.dispatchEvent(
      new CustomEvent("p220:unauthorized"),
    );

    const error = new Error(
      "Tu sesión expiró. Inicia sesión nuevamente.",
    );

    error.status = 401;
    error.data = data;
    throw error;
  }

  if (response.status === 429) {
    const retryAfter =
      response.headers.get("retry-after") ||
      data?.retry_after ||
      "unos segundos";

    const error = new Error(
      `Demasiadas solicitudes. Intenta de nuevo en ${retryAfter}.`,
    );

    error.status = 429;
    error.data = data;
    throw error;
  }

  if (!response.ok) {
    const error = new Error(
      getApiErrorMessage(
        data,
        `Error HTTP ${response.status}`,
      ),
    );

    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

export async function apiRequest(
  path,
  {
    method = "GET",
    body,
    headers,
    authenticated = true,
    signal,
  } = {},
) {
  const response = await fetch(
    `${API_BASE_URL}${path}`,
    {
      method,
      headers: buildHeaders({
        body,
        headers,
        authenticated,
      }),
      body:
        body === undefined
          ? undefined
          : body instanceof FormData
            ? body
            : JSON.stringify(body),
      signal,
      credentials: "omit",
    },
  );

  return validateResponse(response);
}

export async function apiBlobRequest(
  path,
  {
    headers,
    authenticated = true,
    signal,
  } = {},
) {
  const response = await fetch(
    `${API_BASE_URL}${path}`,
    {
      method: "GET",
      headers: buildHeaders({
        headers,
        authenticated,
      }),
      signal,
      credentials: "omit",
    },
  );

  if (!response.ok) {
    await validateResponse(response);
  }

  return response.blob();
}

export { API_BASE_URL };
