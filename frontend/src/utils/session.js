let currentUser = null;

/**
 * El access token viaja exclusivamente en cookie HttpOnly.
 * Viaja en cookie HttpOnly (access_token en desarrollo,
 * __Host-access_token en producción), no accesible por JS.
 * Los datos visuales del usuario viven únicamente en memoria.
 */
export function saveSession({
  user,
}) {
  currentUser = user ?? null;
}

/**
 * @deprecated El token se lee desde cookie HttpOnly en el backend.
 * Mantenido para compatibilidad con código que no haya migrado.
 */
export function getAccessToken() {
  return null;
}

/**
 * Obtiene los datos básicos del usuario almacenado.
 */
export function getStoredUser() {
  return currentUser;
}

/**
 * Indica si existe una sesión local.
 */
export function hasSession() {
  return Boolean(
    getStoredUser(),
  );
}

/**
 * Elimina completamente la sesión local.
 */
export function clearSession() {
  currentUser = null;
}
