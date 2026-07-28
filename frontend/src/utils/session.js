const USER_KEY =
  "p220_user";

/**
 * ✅ M-01 FIX: El access token ya no se almacena en sessionStorage.
 * Viaja en cookie HttpOnly __Host-access_token, no accesible por JS.
 * Solo guardamos datos básicos no sensibles del usuario.
 */
export function saveSession({
  user,
}) {
  sessionStorage.setItem(
    USER_KEY,
    JSON.stringify(
      user ?? null,
    ),
  );
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
    getStoredUser(),
  );
}

/**
 * Elimina completamente la sesión local.
 */
export function clearSession() {
  sessionStorage.removeItem(
    USER_KEY,
  );
}