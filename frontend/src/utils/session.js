const ACCESS_TOKEN_KEY =
  "p220_access_token";

const USER_KEY =
  "p220_user";

/**
 * Guarda el access token y los datos básicos del usuario.
 *
 * sessionStorage:
 * - conserva la información al recargar;
 * - mantiene la sesión mientras la pestaña siga abierta;
 * - elimina la información al cerrar la pestaña;
 * - no comparte automáticamente la sesión con otras pestañas.
 */
export function saveSession({
  accessToken,
  user,
}) {
  const normalizedToken =
    String(
      accessToken || "",
    ).trim();

  if (!normalizedToken) {
    throw new Error(
      "El servidor no devolvió un token de acceso válido.",
    );
  }

  sessionStorage.setItem(
    ACCESS_TOKEN_KEY,
    normalizedToken,
  );

  sessionStorage.setItem(
    USER_KEY,
    JSON.stringify(
      user ?? null,
    ),
  );
}

/**
 * Obtiene el access token almacenado.
 */
export function getAccessToken() {
  const token =
    sessionStorage.getItem(
      ACCESS_TOKEN_KEY,
    );

  return token
    ? token.trim()
    : null;
}

/**
 * Obtiene los datos del usuario almacenado.
 */
export function getStoredUser() {
  const rawUser =
    sessionStorage.getItem(
      USER_KEY,
    );

  if (!rawUser) {
    return null;
  }

  try {
    return JSON.parse(
      rawUser,
    );
  } catch {
    clearSession();
    return null;
  }
}

/**
 * Indica si existe una sesión local.
 */
export function hasSession() {
  return Boolean(
    getAccessToken(),
  );
}

/**
 * Elimina completamente la sesión local.
 */
export function clearSession() {
  sessionStorage.removeItem(
    ACCESS_TOKEN_KEY,
  );

  sessionStorage.removeItem(
    USER_KEY,
  );
}