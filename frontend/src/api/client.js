import {
  clearSession,
  getAccessToken,
} from "../utils/session";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

function buildHeaders({ body, headers = {}, authenticated = true }) {
  const nextHeaders = new Headers(headers);

  if (body !== undefined && !(body instanceof FormData)) {
    nextHeaders.set("Content-Type", "application/json");
  }

  if (authenticated) {
    const token = getAccessToken();

    if (!token) {
      throw new Error("Tu sesión terminó. Inicia sesión nuevamente.");
    }

    nextHeaders.set("Authorization", `Bearer ${token}`);
  }

  nextHeaders.set("X-Request-ID", crypto.randomUUID());

  return nextHeaders;
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : { detail: await response.text() };

  if (response.status === 401) {
    clearSession();
    window.dispatchEvent(new CustomEvent("p220:unauthorized"));
    throw new Error("Tu sesión expiró. Inicia sesión nuevamente.");
  }

  if (response.status === 429) {
    const retryAfter =
      response.headers.get("retry-after") ||
      data.retry_after ||
      "unos segundos";

    throw new Error(
      `Demasiadas solicitudes. Intenta de nuevo en ${retryAfter}.`
    );
  }

  if (!response.ok) {
    throw new Error(
      data.detail ||
      data.message ||
      data.error ||
      `Error HTTP ${response.status}`
    );
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
  } = {}
) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
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
  });

  return parseResponse(response);
}

export { API_BASE_URL };
