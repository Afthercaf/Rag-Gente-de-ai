/**
 * Session Manager — Pizzería 220 AI
 * 
 * Manejo de sesión SEGURO usando cookies HttpOnly.
 * 
 * IMPORTANTE: Los tokens JWT NO se almacenan en localStorage.
 * El backend los setea como cookies HttpOnly (no accesibles desde JS).
 * 
 * Flujo:
 * 1. Login → Backend setea cookies HttpOnly (access_token + refresh_token)
 * 2. Cada request → Axios envía cookies automáticamente (withCredentials: true)
 * 3. 401 → Interceptor de client.js hace refresh automático
 * 4. Logout → Backend elimina cookies
 */

const USER_KEY = "p220_user_metadata";

// ============================================================================
// INFORMACIÓN DEL USUARIO (NO SENSIBLE)
// ============================================================================

/**
 * Guarda metadatos del usuario (NO el token).
 * Solo datos públicos como nombre, email, rol.
 */
export function saveSession({ accessToken, user }) {
  if (!accessToken || typeof accessToken !== "string") {
    throw new Error("El servidor no devolvió un token válido.");
  }

  // NO guardar access_token en localStorage
  // El backend lo maneja como cookie HttpOnly
  
  // Guardar solo metadatos del usuario (nombre, email, rol - NO sensible)
  if (user) {
    const safeUser = {
      nombre: user.nombre,
      gmail: user.gmail,
      role: user.role,
    };
    localStorage.setItem(USER_KEY, JSON.stringify(safeUser));
  }
}

/**
 * Obtiene el access token.
 * 
 * NOTA: El token real está en cookie HttpOnly (no accesible desde JS).
 * Esta función se mantiene por compatibilidad con código existente,
 * pero el token real se envía automáticamente en las cookies.
 * 
 * @returns {string|null} Siempre retorna null (el token está en cookie)
 */
export function getAccessToken() {
  // El token está en cookie HttpOnly, no en localStorage
  // El interceptor de axios (withCredentials: true) lo envía automáticamente
  return null;
}

/**
 * Obtiene metadatos del usuario almacenados localmente.
 * Solo contiene datos NO sensibles (nombre, email, rol).
 */
export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw);
  } catch {
    clearSession();
    return null;
  }
}

/**
 * Limpia la sesión local.
 * 
 * NOTA: Las cookies HttpOnly las elimina el backend en /auth/logout.
 * Esta función solo limpia los metadatos locales del usuario.
 */
export function clearSession() {
  localStorage.removeItem(USER_KEY);
}

/**
 * Verifica si hay una sesión activa.
 * 
 * NOTA: Como el token está en cookie HttpOnly, no podemos verificarlo
 * desde JS. Esta función verifica si hay metadatos de usuario guardados.
 * La verificación real la hace el backend en /auth/me.
 * 
 * @returns {boolean} true si hay metadatos de usuario
 */
export function hasSession() {
  return Boolean(localStorage.getItem(USER_KEY));
}